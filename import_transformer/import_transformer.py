import importlib
import sys
import os
import inspect
import ntpath
from ast import (NodeTransformer, Import, Expr, Call, Name, Load, Str, parse, Attribute, Assign, Store, Module,
                 fix_missing_locations, alias, If, Dict, Not, UnaryOp)
import logging

import astor


BASE_PATH = os.path.dirname(os.path.abspath(__file__))
logger = logging.getLogger(__name__)

IMPORT_ALL = '*'


class ImportsTransformer(NodeTransformer):
    """ Performs transformation of the imported modules and objects of the provided file. """
    types_imported = False

    def __init__(self, transform_package_path='/'):
        """
        Initialize import transformer.
        transform_package_path: Defines path under which imports will be transformed.
        """
        super(ImportsTransformer).__init__()
        self.transform_package_path = os.path.abspath(transform_package_path)
        self.initialized = {}

    @property
    def is_modified(self):
        """ If that flag is True the sources was modified. """
        return self.types_imported

    def _to_transform(self, node):
        """ Checks whether import shall be transformed. """
        module_path = getattr(node, 'module', '')
        if not module_path:
            module_path = node.names[0].name
        module = importlib.import_module(module_path)
        return module_path not in sys.builtin_module_names and self.transform_package_path in module.__file__

    def get_sources(self, path):
        """ Returns the sources of selected module. If the sources aren't available ( init file) returns None. """
        module = importlib.import_module(path)
        sources = inspect.getsource(module)
        # The sources of importing module may contain imports which suppose to be replaced to.
        sources_ast = ImportsTransformer(self.transform_package_path).visit(parse(sources, path))
        sources = astor.to_source(sources_ast, indent_with=' ' * 4, add_line_information=False)
        return sources

    def get_transformed_import(self, node):
        """ Emulates importing of the module or it's constants. . """
        replacing_node_body = self.get_replacing_node_body()
        node_modules_map = self.get_node_modules(node)  # from package import subpackage, ClassA, FuncD

        for node_name, node_info in node_modules_map.items():
            sources = self.get_sources(node_info['path'])
            if sources is None:
                continue

            replacing_node_body.append(Expr(value=Call(func=Name(id='print', ctx=Load()),
                                                       args=[Str(s=astor.to_source(node))],
                                                       keywords=[])))
            # for from foo.bar import *
            if node_name == IMPORT_ALL:
                replacing_node_body.append(Expr(value=Call(
                    func=Name(id='exec', ctx=Load()),
                    args=[Str(s=sources), Call(func=Name(id='locals', ctx=Load()), args=[], keywords=[])],
                    keywords=[]))
                )
                continue
            if not self.initialized.get(node_info['path']):
                replacing_node_body += self.get_module_assignments(node_info['path'])
                replacing_node_body.append(Expr(value=Call(func=Name(id='exec', ctx=Load()),
                                                           args=[Str(s=sources),
                                                                 Attribute(value=Name(id=node_info['path'], ctx=Load()),
                                                                           attr='__dict__',
                                                                           ctx=Load())], keywords=[])))
                self.initialized[node_info['path']] = True
            # for import foo.bar.baz, but not import foo.bar.baz as fbz
            if node_name == node_info['path'] and not node_info['alias']:
                continue
            value = None
            items = node_name.split('.')
            for index, item in enumerate(items[:-1]):
                value = Attribute(value=value or Name(id=item, ctx=Load()),
                                  attr=items[index + 1], ctx=Load())
            # for from coco import bunny
            if value is None:
                if node_info['is_module']:
                    value = Name(id=node_info['path'], ctx=Load())
                else:
                    value = Attribute(value=Name(id=node_info['path'], ctx=Load()),
                                      attr=node_name, ctx=Load())
            identifier = node_info['alias'] or node_name
            assign_node = Assign(targets=[Name(id=identifier, ctx=Store())], value=value)

            replacing_node_body.append(assign_node)

        replacing_node = Module(body=replacing_node_body)
        return replacing_node if replacing_node_body else node

    @staticmethod
    def get_module_assignments(node_info_path):
        """ Returns module assignment nodes which declare ModuleType object in case
        if this object has not been declared in the current scope. """
        target_id = ''
        module_assignments = []
        for item in node_info_path.split('.'):
            target_id += f'.{item}' if target_id else item
            target = Name(id=target_id, ctx=Store())

            is_module_imported = None
            scope = Call(func=Name(id='locals'), args=[], keywords=[])
            for path_part in target_id.split('.'):
                is_module_imported = Call(func=Attribute(value=scope, attr='get'),
                                          args=[Str(s=path_part), Dict(keys=[], values=[])],
                                          keywords=[])
                scope = Attribute(value=is_module_imported, attr='__dict__', ctx=Load())
            is_module_imported = Call(func=Name(id='isinstance', ctx=Load()),
                                      args=[is_module_imported, Attribute(value=Name(id='types', ctx=Load()),
                                                                          attr='ModuleType', ctx=Load())],
                                      keywords=[])
            module_assignments.append(
                If(test=UnaryOp(Not(), is_module_imported),
                    body=[Assign(targets=[target], value=Call(func=Attribute(value=Name(id='types', ctx=Load()),
                                                                             attr='ModuleType', ctx=Load()),
                                                              args=[Str(s=target.id), Str(s=f'The {target.id} module')],
                                                              keywords=[]))], orelse=[]))
        return module_assignments

    def get_node_modules(self, node):
        """
        Process all importing items and build node modules and objects map.
        :return dict {
            'name': {
                path: path to the sources,
                alias: alias used in the import,
                from_module: the root package of the module}
        }
        """
        if getattr(node, 'module', ''):
            node_module = f'{node.module}'
        else:
            # assert len(node.names) == 1
            node_module = ''
        modules = {}

        for module_candidate in node.names:
            try:
                module_path = f'{node_module}.{module_candidate.name}' if node_module else module_candidate.name
                importlib.import_module(module_path)
                modules[module_candidate.name] = {'path': module_path, 'alias': module_candidate.asname,
                                                  'from_module': node_module, 'is_module': True}
            except ModuleNotFoundError:
                # Importing of an object met.
                modules[module_candidate.name] = {'path': node_module, 'alias': module_candidate.asname,
                                                  'from_module': node_module, 'is_module': False}
        return modules

    def get_replacing_node_body(self) -> 'list':
        """ Returns replacing node body, which is [] or [ImportNode], where ImportNode = 'import types',
        used for further imports transformation and shall be imported once. """
        replacing_node_body = []
        if not self.types_imported:
            replacing_node_body.append(Import(names=[alias(name='types', asname=None)]))
            self.types_imported = True
        return replacing_node_body

    def visit_Import(self, node):
        if not self._to_transform(node):
            return node
        node = self.get_transformed_import(node)
        fix_missing_locations(node)
        return node

    def visit_ImportFrom(self, node):
        if not self._to_transform(node):
            return node
        node = self.get_transformed_import(node)
        fix_missing_locations(node)
        return node

    def transform_file_imports(self, fpath):
        with open(fpath) as fh:
            initial_sources = fh.read()
        root = parse(initial_sources, fpath)
        try:
            # Changing directory for correct processing of relative imports.
            sys.path.insert(0, os.path.dirname(fpath))
            self.visit(root)
        except Exception as exc:
            raise exc
        finally:
            sys.path.pop(0)

        if not self.is_modified:
            logger.info('File %s has no local subpackage dependencies. The transformation skipped.', fpath)
            return initial_sources
        logger.info('Completed import transformation of %s .', fpath)
        sources = astor.to_source(root, indent_with=' ' * 4, add_line_information=False)
        fname = ntpath.basename(fpath)
        with open(os.path.join(self.transform_package_path, 'tmp', 'transformed_imports_{}'.format(fname)), 'w+') as out:
            out.write(sources)
        return sources
