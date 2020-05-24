#!/usr/bin/env python

"""
distutils/setuptools install script.
"""
import os
import re

from setuptools import setup, find_packages


ROOT = os.path.dirname(__file__)
VERSION_RE = re.compile(r'''__version__ = ['"]([0-9.]+)['"]''')


def get_version():
    init = open(os.path.join(ROOT, 'import_transformer', '__init__.py')).read()
    return VERSION_RE.search(init).group(1)


setup(
    name='import_transformer',
    version=get_version(),
    description='Implements import transformer to replace module imports.',
    long_description=open('README.md').read(),
    author='Andriy Ivaneyko',
    url='https://github.com/',
    scripts=[],
    packages=find_packages(),
    install_requires=['astor'],
    include_package_data=True,
    license="Apache License 2.0",
    classifiers=[
        'Natural Language :: English',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
)