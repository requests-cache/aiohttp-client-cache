import asyncio
from contextlib import asynccontextmanager
from sys import version_info
from typing import AsyncIterator

import pytest
from aioredis import create_redis_pool

from aiohttp_client_cache.backends.redis import DEFAULT_ADDRESS, RedisBackend, RedisCache
from aiohttp_client_cache.session import CachedSession
from test.integration import BaseBackendTest, BaseStorageTest


def is_db_running():
    """Test if a Redis server is running locally on the default port"""

    async def get_db_info():
        client = await create_redis_pool(DEFAULT_ADDRESS)
        await client.info()
        client.close()
        await client.wait_closed()

    try:
        asyncio.run(get_db_info())
        return True
    except OSError:
        return False


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        version_info >= (3, 10) or not is_db_running(),
        reason='Redis server required for integration tests',
    ),
]


class TestRedisCache(BaseStorageTest):
    storage_class = RedisCache
    picklable = True


class TestRedisBackend(BaseBackendTest):
    backend_class = RedisBackend

    @asynccontextmanager
    async def init_session(self, **kwargs) -> AsyncIterator[CachedSession]:
        async with super().init_session(**kwargs) as session:
            yield session
        await session.cache.close()
