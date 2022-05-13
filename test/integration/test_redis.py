import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

import pytest
from redis.asyncio import from_url

from aiohttp_client_cache.backends.redis import DEFAULT_ADDRESS, RedisBackend, RedisCache
from aiohttp_client_cache.session import CachedSession
from test.integration import BaseBackendTest, BaseStorageTest


def is_db_running():
    """Test if a Redis server is running locally on the default port"""

    async def get_db_info():
        client = await from_url(DEFAULT_ADDRESS)
        await client.info()
        await client.close()

    try:
        asyncio.run(get_db_info())
        return True
    except OSError as e:
        print(e)
        return False


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        not is_db_running(),
        reason='Redis server required for integration tests',
    ),
]


class TestRedisCache(BaseStorageTest):
    storage_class = RedisCache
    picklable = True


class TestRedisBackend(BaseBackendTest):
    backend_class = RedisBackend

    @asynccontextmanager
    async def init_session(self, **kwargs) -> AsyncIterator[CachedSession]:  # type: ignore
        async with super().init_session(**kwargs) as session:
            yield session
        await session.cache.close()
