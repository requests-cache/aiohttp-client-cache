import pytest
from contextlib import contextmanager
from logging import basicConfig, getLogger
from tempfile import NamedTemporaryFile
from typing import Iterator

from aiohttp_client_cache import CachedSession, SQLiteBackend

ALL_METHODS = ['GET', 'HEAD', 'OPTIONS', 'POST', 'PUT', 'PATCH', 'DELETE']

# Configure logging for pytest session
basicConfig(level='INFO')
getLogger('aiohttp_client_cache').setLevel('DEBUG')


# @pytest.fixture(scope='function')
@contextmanager
def tempfile_session(**kwargs) -> Iterator[CachedSession]:
    """Get a CachedSession using a temporary SQLite db"""
    with NamedTemporaryFile(suffix='.db') as temp:
        cache = SQLiteBackend(cache_name=temp.name, allowed_methods=ALL_METHODS, **kwargs)
        yield CachedSession(cache=cache)
