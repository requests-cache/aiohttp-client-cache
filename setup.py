#!/usr/bin/env python
from setuptools import setup, find_packages
from aiohttp_client_cache import __version__


setup(
    name='aiohttp-client-cache',
    packages=find_packages(),
    include_package_data=True,
    version=__version__,
    author='Roman Haritonov',
    author_email='reclosedev@gmail.com',
    url='https://github.com/JWCook/aiohttp-client-cache',
    install_requires=['aiohttp', 'attrs', 'python-dateutil'],
    extras_require={
        'dev': [
            'black==20.8b1',
            'boto3',
            'pytest',
            'pytest-cov',
            'pymongo<=3.0',
            'redis',
        ]
    },
)
