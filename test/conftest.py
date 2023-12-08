import logging
from contextlib import asynccontextmanager
from datetime import datetime
from os import getenv
from tempfile import NamedTemporaryFile
from typing import AsyncIterator

import pytest

from aiohttp_client_cache import CachedResponse, CachedSession, SQLiteBackend

ALL_METHODS = ['GET', 'HEAD', 'OPTIONS', 'POST', 'PUT', 'PATCH', 'DELETE']
CACHE_NAME = 'pytest_cache'
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

HTTPDATE_STR = 'Fri, 16 APR 2021 21:13:00 GMT'
HTTPDATE_DATETIME = datetime(2021, 4, 16, 21, 13)


# Configure logging for pytest session
logging.basicConfig(level='INFO')
# logging.getLogger('aiohttp_client_cache').setLevel('DEBUG')


def from_cache(*responses) -> bool:
    """Indicate whether one or more responses came from the cache"""
    return all(isinstance(response, CachedResponse) for response in responses)


def httpbin(path: str = ''):
    """Get the url for either a local or remote httpbin instance"""
    base_url = getenv('HTTPBIN_URL', 'http://localhost:8080/')
    return base_url + path


def httpbin_custom(path: str = ''):
    """Get the url for a local httpbin_custom instance"""
    base_url = 'http://localhost:8181/'
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


def assert_delta_approx_equal(dt1: datetime, dt2: datetime, target_delta, threshold_seconds=2):
    """Assert that the given datetimes are approximately ``target_delta`` seconds apart"""
    diff_in_seconds = (dt2 - dt1).total_seconds()
    assert abs(diff_in_seconds - target_delta) <= threshold_seconds
