import os
from datetime import datetime
from tempfile import NamedTemporaryFile, gettempdir

import pytest

from aiohttp_client_cache.backends.sqlite import SQLiteBackend, SQLiteCache, SQLitePickleCache

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


def test_backend_init():
    with NamedTemporaryFile(suffix='.db') as temp:
        backend = SQLiteBackend(cache_name=temp.name)
        assert backend.responses.filename == temp.name
        assert backend.redirects.filename == temp.name


async def test_bulk_commit(cache_client):
    async with cache_client.bulk_commit():
        for i in range(1000):
            await cache_client.write(f'key_{i}', str(i))

    assert await cache_client.size() == 1000


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

    assert {k async for k in cache_client.keys()} == set(test_data.keys())
    assert {v async for v in cache_client.values()} == set(test_data.values())


async def test_size(cache_client):
    for k, v in test_data.items():
        await cache_client.write(k, v)

    assert await cache_client.size() == len(test_data)


async def test_clear(cache_client):
    for k, v in test_data.items():
        await cache_client.write(k, v)

    await cache_client.clear()
    assert await cache_client.size() == 0
    assert {k async for k in cache_client.keys()} == set()
    assert {v async for v in cache_client.values()} == set()


def test_use_temp():
    relative_path = SQLiteCache('test-db', 'test-table').filename
    temp_path = SQLiteCache('test-db', 'test-table', use_temp=True).filename
    assert not relative_path.startswith(gettempdir())
    assert temp_path.startswith(gettempdir())
