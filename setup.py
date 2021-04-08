#!/usr/bin/env python
from itertools import chain
from setuptools import find_packages, setup

from aiohttp_client_cache import __version__

extras_require = {
    # Packages used for CI jobs
    'build': ['coveralls', 'twine', 'wheel'],
    # Packages for all supported backends
    'backends': ['aiosqlite', 'aioboto3', 'motor', 'aioredis'],
    # Packages used for documentation builds
    'docs': [
        'm2r2~=0.2.5',
        'docutils==0.16',
        'Sphinx~=3.5.3',
        'sphinx-autodoc-typehints',
        'sphinx-copybutton',
        'sphinx-material',
        'sphinxcontrib-apidoc',
    ],
    # Packages used for testing both locally and in CI jobs
    'test': [
        'black==20.8b1',
        'flake8',
        'isort',
        'mypy',
        'pre-commit',
        'pytest>=5.0',
        'pytest-aiohttp',
        'pytest-asyncio',
        'pytest-cov',
    ],
}
# All development/testing packages combined
extras_require['dev'] = list(chain.from_iterable(extras_require.values()))

setup(
    name='aiohttp-client-cache',
    packages=find_packages(),
    include_package_data=True,
    version=__version__,
    install_requires=['aiohttp', 'attrs', 'itsdangerous', 'python-forge', 'url-normalize'],
    extras_require=extras_require,
    zip_safe=False,
)
