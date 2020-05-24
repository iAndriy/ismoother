import os
import ast
from unittest import TestCase, mock

import astor

from import_transformer import ImportsTransformer


# {Key:Value} dictionary where key is string representation of the python import statement and
# value is the tuple of next format: (expected out, mocking information)
TRANSFORMING_IMPORTS = {
    "from somepackage.constants import SOME_CONSTANT": (
        ast.parse("""import types\n
print('from somepackage.constants import SOME_CONSTANT\\n')\n
somepackage = types.ModuleType('somepackage', 'The somepackage module')\n
somepackage.constants = types.ModuleType('somepackage.constants', 'The somepackage.constants module')\n
exec(\"""SOME_CONSTANT = 'some_id'\""" , somepackage.constants.__dict__)\n
SOME_CONSTANT = somepackage.constants.SOME_CONSTANT\n"""),
        {'get_module_assignments': ast.parse("""
somepackage = types.ModuleType('somepackage', 'The somepackage module')\n
somepackage.constants = types.ModuleType('somepackage.constants', 'The somepackage.constants module')
""").body,
         'get_node_modules': {'SOME_CONSTANT': {'path': 'somepackage.constants', 'alias': None,
                                                          'from_module': 'somepackage.constants',
                                                          'is_module': False}},
         'get_sources': "SOME_CONSTANT = 'some_id'",
         'get_replacing_node_body': ast.parse("import types").body
         }
    ),
    "from somepackage.submod.some_class import SomeClass": (
        ast.parse("""print('from somepackage.submod.some_class import SomeClass\\n')\n
somepackage = types.ModuleType('somepackage', 'The somepackage module')\n
somepackage.submod = types.ModuleType('somepackage.submod', 'The somepackage.submod module')\n
somepackage.submod.some_class = types.ModuleType('somepackage.submod.some_class', \n
'The somepackage.submod.some_class module')\n
exec(\"""class SomeClass: pass\""" , somepackage.submod.some_class.__dict__)\n
SomeClass = somepackage.submod.some_class.SomeClass\n"""),
        {'get_module_assignments': ast.parse("""
somepackage = types.ModuleType('somepackage', 'The somepackage module')\n
somepackage.submod = types.ModuleType('somepackage.submod', 'The somepackage.submod module')\n
somepackage.submod.some_class = types.ModuleType('somepackage.submod.some_class', \n
'The somepackage.submod.some_class module')\n
""").body,
         'get_node_modules': {'SomeClass': {'path': 'somepackage.submod.some_class', 'alias': None,
                                                   'from_module': 'somepackage.submod.some_class',
                                                   'is_module': False}},
         'get_sources': "class SomeClass: pass",
         'get_replacing_node_body': []}
    ),
    "from somepackage.submod.some_class import SomeClass as nn": (
        ast.parse("""
print('from somepackage.submod.some_class import SomeClass as nn\\n')\n
somepackage = types.ModuleType('somepackage', 'The somepackage module')\n
somepackage.submod = types.ModuleType('somepackage.submod', 'The somepackage.submod module')\n
somepackage.submod.some_class = types.ModuleType('somepackage.submod.some_class', \n
'The somepackage.submod.some_class module')\n
exec(\"""class SomeClass: pass\""" , somepackage.submod.some_class.__dict__)\n
nn = somepackage.submod.some_class.SomeClass\n"""),
        {'get_module_assignments': ast.parse("""
somepackage = types.ModuleType('somepackage', 'The somepackage module')\n
somepackage.submod = types.ModuleType('somepackage.submod', 'The somepackage.submod module')\n
somepackage.submod.some_class = types.ModuleType('somepackage.submod.some_class', \n
'The somepackage.submod.some_class module')\n
""").body,
         'get_node_modules': {'SomeClass': {'path': 'somepackage.submod.some_class', 'alias': 'nn',
                                                   'from_module': 'somepackage.submod.some_class',
                                                   'is_module': False}},
         'get_sources': "class SomeClass: pass",
         'get_replacing_node_body': []
         }
    ),

    "import somepackage.constants": (
        ast.parse("""
print('import somepackage.constants\\n')\n
somepackage = types.ModuleType('somepackage', 'The somepackage module')\n
somepackage.constants = types.ModuleType('somepackage.constants', 'The somepackage.constants module')\n
exec(\"""BETA = 2\nZETA = 3\""", somepackage.constants.__dict__)\n
"""),
        {'get_module_assignments': ast.parse("""
somepackage = types.ModuleType('somepackage', 'The somepackage module')\n
somepackage.constants = types.ModuleType('somepackage.constants', 'The somepackage.constants module')\n
""").body,
         'get_node_modules': {'somepackage.constants': {'path': 'somepackage.constants', 'alias': None,
                                                          'from_module': '', 'is_module': True}},
         'get_sources': "BETA = 2\nZETA = 3",
         'get_replacing_node_body': [],
         }),
    "import somepackage.constants as m_constants": (
        ast.parse("""
print('import somepackage.constants as m_constants\\n')\n
somepackage = types.ModuleType('somepackage', 'The somepackage module')\n
somepackage.constants = types.ModuleType('somepackage.constants', 'The somepackage.constants module')\n
exec(\"""BETA = 2\nZETA = 3\""", somepackage.constants.__dict__)\n
m_constants = somepackage.constants\n"""),
        {'get_module_assignments': ast.parse("""
somepackage = types.ModuleType('somepackage', 'The somepackage module')\n
somepackage.constants = types.ModuleType('somepackage.constants', 'The somepackage.constants module')\n
""").body,
         'get_node_modules': {'somepackage.constants': {'path': 'somepackage.constants', 'alias': 'm_constants',
                                                          'from_module': '', 'is_module': True}},
         'get_sources': "BETA = 2\nZETA = 3",
         'get_replacing_node_body': [],
         }
    ),
    "from somepackage.constants import *": (
        ast.parse("""
print('from somepackage.constants import *\\n')\n
exec(\"""BETA = 2\nZETA = 3\""", locals())\n
"""),
        {'get_node_modules': {'*': {'path': 'somepackage.constants', 'alias': None,
                                    'from_module': 'somepackage.constants', 'is_module': False}},
         'get_sources': "BETA = 2\nZETA = 3",
         'get_replacing_node_body': [],
         }
    ),
    "from somepackage.constants import BETA, ZETA, constants": (
        ast.parse("""
print('from somepackage.constants import BETA, ZETA, constants\\n')\n
somepackage = types.ModuleType('somepackage', 'The somepackage module')\n
somepackage.constants = types.ModuleType('somepackage.constants', 'The somepackage.constants module')\n
exec(\"""BETA = 2\nZETA = 3\nconstants=[1, 2, 3]\""", somepackage.constants.__dict__)\n
BETA = somepackage.constants.BETA\n
print('from somepackage.constants import BETA, ZETA, constants\\n')\n
ZETA = somepackage.constants.ZETA\n
print('from somepackage.constants import BETA, ZETA, constants\\n')\n
constants = somepackage.constants.constants\n
"""),
        {'get_module_assignments': ast.parse("""
somepackage = types.ModuleType('somepackage', 'The somepackage module')\n
somepackage.constants = types.ModuleType('somepackage.constants', 'The somepackage.constants module')\n
""").body,
         'get_node_modules': {
             'BETA': {'path': 'somepackage.constants', 'alias': None, 'from_module': 'somepackage.constants',
                      'is_module': False},
             'ZETA': {'path': 'somepackage.constants', 'alias': None, 'from_module': 'somepackage.constants',
                      'is_module': False},
             'constants': {'path': 'somepackage.constants', 'alias': None, 'from_module': 'somepackage.constants',
                           'is_module': False}},
         'get_sources': "BETA = 2\nZETA = 3\nconstants=[1, 2, 3]",
         'get_replacing_node_body': []}
    )
}


class AggregatedImportTransformerMocks(object):
    """ Simple mock agreagator to avoid nested with context managers. """
    mock_path = 'import_transformer.ImportsTransformer'

    def __init__(self, mock_data):
        self.mock_data = mock_data
        self.mocked = []

    def __enter__(self):
        self.mocked = {}
        for mocking_item, return_value in self.mock_data.items():
            self.mocked[mocking_item] = mock.patch('{}.{}'.format(self.mock_path, mocking_item), return_value=return_value)
            self.mocked[mocking_item].start()
        return self.mocked

    def __exit__(self, type, value, traceback):
        for mocked in self.mocked.values():
            mocked.stop()


class TestImportsTransformer(TestCase):
    transformable_imports = TRANSFORMING_IMPORTS.keys()

    def test__init__(self):
        """ Tests initialization of the ImportsTransformer. """
        instance = ImportsTransformer()
        expected = {'transform_package_path': '/', 'initialized': {}}
        self.assertEqual(instance.__dict__, expected)
        self.assertEqual(instance.is_modified, False)

        # Tests relative and abs pathes of transforming package.
        transform_package_path = '../somepackage'
        instance = ImportsTransformer(transform_package_path)
        expected = {'transform_package_path': os.path.abspath(transform_package_path), 'initialized': {}}
        self.assertEqual(instance.__dict__, expected)
        self.assertEqual(instance.is_modified, False)

        transform_package_path = '/tmp/path/to/somepackage'
        instance = ImportsTransformer(transform_package_path)
        expected = {'transform_package_path': transform_package_path, 'initialized': {}}
        self.assertEqual(instance.__dict__, expected)
        self.assertEqual(instance.is_modified, False)

    def test__to_transform_valid_imports(self):
        """ Tests _to_transform for verification that valid imports are going to be taken for transformation. """
        not_transformable_imports = [
            "from itertools import *",
            "import ast",
            "from unittest import TestCase, mock"
        ]
        import_transformer = ImportsTransformer('somepackage')
        for import_str in not_transformable_imports:
            import_node = ast.parse(import_str).body[0]
            self.assertFalse(import_transformer._to_transform(import_node))

        for import_str in self.transformable_imports:
            import_node = ast.parse(import_str).body[0]
            mock_file = mock.MagicMock()
            mock_file.__file__ = {import_transformer.transform_package_path}
            with mock.patch('import_transformer.import_transformer.importlib.import_module', side_effect=mock.MagicMock(side_effect=lambda x: mock_file)):
                self.assertTrue(import_transformer._to_transform(import_node))

    # def test_get_sources(self):
    #     """ Tests getting sources method. """
    #     modules = ['somepackage.constants', 'somepackage.submod.some_class']
    #     import_transformer = ImportsTransformer('../somepackage')
    #     # Convert code to ast and back to avoid difference in indentation.
    #     with mock.patch('import_transformer.ImportsTransformer.visit',
    #                     new=(lambda inst, src: src)):
    #         for module in modules:
    #             actual = import_transformer.get_sources(module)
    #             expected = inspect.getsource(importlib.import_module(module))
    #             actual, expected = astor.to_source(ast.parse(actual)), astor.to_source(ast.parse(expected))
    #             self.assertEqual(actual, expected)

    def test_get_transformed_import(self):
        """ Tests implementation of the imports transformation replacing node body. """
        for import_str, import_info in TRANSFORMING_IMPORTS.items():
            import_node = ast.parse(import_str).body[0]
            expected, transforming_import_data = (import_info[0], import_info[1])
            import_transformer = ImportsTransformer()
            with AggregatedImportTransformerMocks(transforming_import_data):
                actual = import_transformer.get_transformed_import(import_node)
                # Compare actual sources, not ast trees.
                actual, expected = astor.to_source(ast.parse(actual)), astor.to_source(expected)
                self.assertEqual(actual, expected)

    def test_get_module_assignments(self):
        assignments_paths = [('somepackage.constants', ast.parse("""
if not isinstance(locals().get('somepackage', {}), types.ModuleType):
    somepackage = types.ModuleType('somepackage',
        'The somepackage module')
if not isinstance(locals().get('somepackage', {}).__dict__.get(
    'constants', {}), types.ModuleType):
    somepackage.constants = types.ModuleType('somepackage.constants',
        'The somepackage.constants module')
""")), ('somepackage.submod.some_class', ast.parse("""
if not isinstance(locals().get('somepackage', {}), types.ModuleType):
    somepackage = types.ModuleType('somepackage',
        'The somepackage module')
if not isinstance(locals().get('somepackage', {}).__dict__.get('submod', {}
    ), types.ModuleType):
    somepackage.submod = types.ModuleType('somepackage.submod',
        'The somepackage.submod module')
if not isinstance(locals().get('somepackage', {}).__dict__.get('submod', {}
    ).__dict__.get('some_class', {}), types.ModuleType):
    somepackage.submod.some_class = types.ModuleType(
        'somepackage.submod.some_class',
        'The somepackage.submod.some_class module')
"""))]
        for assignment_path, expected in assignments_paths:
            actual = ImportsTransformer().get_module_assignments(assignment_path)
            actual, expected = astor.to_source(ast.Module(body=actual)), astor.to_source(expected)
            self.assertEqual(actual, expected)

    def test_get_replacing_node_body(self):
        """ Tests getting replacing node body. """
        transformer = ImportsTransformer()
        actual = transformer.get_replacing_node_body()
        actual, expected = astor.to_source(ast.Module(body=actual)), "import types\n"
        self.assertEqual(actual, expected)

        # Calling method more than once shall return [] as the import types shall be done only once.
        actual = transformer.get_replacing_node_body()
        expected = []
        self.assertEqual(actual, expected)

    @mock.patch("builtins.open", mock.mock_open(read_data="import pdb"))
    @mock.patch("import_transformer.import_transformer.logger")
    def test_transform_file_imports(self, *args):
        """ Tests starting of the file processing. """
        transformer = ImportsTransformer()
        with mock.patch('import_transformer.ImportsTransformer.visit',
                        new=(lambda inst, src: src)):
            actual = transformer.transform_file_imports('/tmp/some_file.py')
            expected = 'import pdb'
            self.assertEqual(actual, expected)

        # Test transformer moved to modified state.
        with mock.patch('import_transformer.ImportsTransformer.visit',
                        new=(lambda inst, src: src)):
            with mock.patch('import_transformer.ImportsTransformer.is_modified',
                            return_value=True):
                actual = transformer.transform_file_imports('/tmp/some_file.py')
                expected = 'import pdb\n'
                self.assertEqual(actual, expected)
