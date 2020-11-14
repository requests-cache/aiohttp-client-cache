#!/usr/bin/env python
from setuptools import setup, find_packages


setup(
    name='aiohttp-client-cache',
    packages=find_packages(),
    include_package_data=True,
    version='0.5.2',
    author='Roman Haritonov',
    author_email='reclosedev@gmail.com',
    url='https://github.com/JWCook/aiohttp-client-cache',
    install_requires=['aiohttp'],
    extras_require={
        'dev': [
            'pytest',
            'pytest-cov',
            'pymongo',
            'redis',
        ]
    },
)
