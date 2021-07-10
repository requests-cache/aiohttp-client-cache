import asyncio
from datetime import datetime
from sys import version_info

import pytest
from aioredis import create_redis_pool

from aiohttp_client_cache.backends.redis import DEFAULT_ADDRESS, RedisBackend, RedisCache


def is_db_running():
    """Test if a Redis server is running locally on the default port"""

    async def get_db_info():
        client = await create_redis_pool('redis://localhost')
        await client.info()

    try:
        asyncio.run(get_db_info())
        return True
    except OSError:
        return False


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        version_info > (3, 9) or not is_db_running(),
        reason='Redis server required for integration tests',
    ),
]

test_data = {'key_1': 'item_1', 'key_2': datetime.now(), 'key_3': 3.141592654}


@pytest.fixture(autouse=True, scope='function')
async def cache_client():
    """Fixture that creates a new db client for each test function"""
    cache_client = RedisCache('aiohttp-cache', 'responses', 'redis://localhost')
    await cache_client.clear()
    yield cache_client
    await cache_client.clear()


def test_backend_init():
    backend = RedisBackend()
    assert backend.responses.address == DEFAULT_ADDRESS
    assert backend.responses.hash_key == 'aiohttp-cache:responses'
    assert backend.redirects.hash_key == 'aiohttp-cache:redirects'


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
    assert {k async for k in cache_client.keys()} == set(test_data.keys())
    assert {v async for v in cache_client.values()} == set(test_data.values())


async def test_clear(cache_client):
    for k, v in test_data.items():
        await cache_client.write(k, v)

    await cache_client.clear()
    assert await cache_client.size() == 0
    assert {k async for k in cache_client.keys()} == set()
    assert {v async for v in cache_client.values()} == set()
