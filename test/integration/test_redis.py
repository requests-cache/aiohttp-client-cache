from __future__ import annotations
import asyncio

import pytest
from redis.asyncio import from_url

from aiohttp_client_cache.backends.redis import DEFAULT_ADDRESS, RedisBackend, RedisCache
from test.integration import BaseBackendTest, BaseStorageTest


def is_db_running():
    """Test if a Redis server is running locally on the default port"""

    async def get_db_info():
        client = await from_url(DEFAULT_ADDRESS)
        await client.info()
        await client.aclose()  # type: ignore[attr-defined]

    try:
        asyncio.run(get_db_info())
        return True
    except OSError as e:
        print(e)
        return False


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not is_db_running(), reason='Redis server required for integration tests'),
]


class TestRedisCache(BaseStorageTest):
    storage_class = RedisCache
    picklable = True


class TestRedisBackend(BaseBackendTest):
    backend_class = RedisBackend
