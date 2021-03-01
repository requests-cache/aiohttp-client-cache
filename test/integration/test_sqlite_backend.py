import pytest
from datetime import datetime
from tempfile import NamedTemporaryFile

from aiohttp_client_cache.backends.sqlite import SQLiteBackend, SQLitePickleCache

pytestmark = pytest.mark.asyncio
test_data = {'key_1': 'item_1', 'key_2': datetime.now(), 'key_3': 3.141592654}


@pytest.fixture(autouse=True, scope='function')
async def cache_client():
    """Fixture that creates a new db client for each test function"""
    with NamedTemporaryFile(suffix='.db') as temp:
        cache_client = SQLitePickleCache(temp.name, 'responses')
        await cache_client.clear()
        yield cache_client
        await cache_client.clear()


def test_sqlite_backend():
    with NamedTemporaryFile(suffix='.db') as temp:
        backend = SQLiteBackend(cache_name=temp.name)
        assert backend.responses.filename == temp.name
        assert backend.redirects.filename == temp.name


async def test_write_read(cache_client):
    # Test write() and contains()
    for k, v in test_data.items():
        await cache_client.write(k, v)
        assert await cache_client.contains(k) is True

    # Test read()
    for k, v in test_data.items():
        assert await cache_client.read(k) == v


async def test_delete(cache_client):
    for k, v in test_data.items():
        await cache_client.write(k, v)

    for k in test_data.keys():
        await cache_client.delete(k)
        assert await cache_client.contains(k) is False


async def test_keys_values_size(cache_client):
    for k, v in test_data.items():
        await cache_client.write(k, v)

    assert await cache_client.size() == len(test_data)
    assert await cache_client.keys() == list(test_data.keys())
    assert await cache_client.values() == list(test_data.values())


async def test_clear(cache_client):
    for k, v in test_data.items():
        await cache_client.write(k, v)

    await cache_client.clear()
    assert await cache_client.size() == 0
    assert await cache_client.keys() == []
    assert await cache_client.values() == []
