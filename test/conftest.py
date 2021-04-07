import pytest
from contextlib import asynccontextmanager
from logging import basicConfig, getLogger
from os import getenv
from tempfile import NamedTemporaryFile
from typing import AsyncIterator

from aiohttp_client_cache import CachedResponse, CachedSession, SQLiteBackend

ALL_METHODS = ['GET', 'HEAD', 'OPTIONS', 'POST', 'PUT', 'PATCH', 'DELETE']
HTTPBIN_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
HTTPBIN_FORMATS = [
    'brotli',
    'deflate',
    'deny',
    'encoding/utf8',
    'gzip',
    'html',
    'image/jpeg',
    'image/png',
    'image/svg',
    'image/webp',
    'json',
    'robots.txt',
    'xml',
]


# Configure logging for pytest session
basicConfig(level='INFO')
getLogger('aiohttp_client_cache').setLevel('DEBUG')


def from_cache(*responses) -> bool:
    """Indicate whether one or more responses came from the cache"""
    return all([isinstance(response, CachedResponse) for response in responses])


def httpbin(path):
    """Get the url for either a local or remote httpbin instance"""
    base_url = getenv('HTTPBIN_URL', 'http://localhost:80/')
    return base_url + path


@pytest.fixture(scope='function')
async def tempfile_session():
    """:py:func:`.get_tempfile_session` as a pytest fixture"""
    async with get_tempfile_session() as session:
        yield session


@asynccontextmanager
async def get_tempfile_session(**kwargs) -> AsyncIterator[CachedSession]:
    """Get a CachedSession using a temporary SQLite db"""
    with NamedTemporaryFile(suffix='.db') as temp:
        cache = SQLiteBackend(cache_name=temp.name, allowed_methods=ALL_METHODS, **kwargs)
        async with CachedSession(cache=cache) as session:
            yield session
