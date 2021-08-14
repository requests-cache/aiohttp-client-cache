from datetime import datetime
from typing import Dict, Type

import pytest

from aiohttp_client_cache.backends.sqlite import BaseCache
from test.conftest import CACHE_NAME

pytestmark = pytest.mark.asyncio
test_data = {'key_1': 'item_1', 'key_2': datetime(2021, 8, 14), 'key_3': 3.141592654}


class BaseStorageTest:
    """Base class for testing cache storage dict-like interfaces"""

    storage_class: Type[BaseCache] = None  # type: ignore
    init_kwargs: Dict = {}
    picklable: bool = False

    async def init_cache(self, index=0, **kwargs):
        cache = self.storage_class(CACHE_NAME, f'table_{index}', **self.init_kwargs, **kwargs)
        await cache.clear()
        return cache

    async def test_write_read(self):
        cache = await self.init_cache()
        # Test write() and contains()
        for k, v in test_data.items():
            await cache.write(k, v)
            assert await cache.contains(k) is True

        # Test read()
        for k, v in test_data.items():
            assert await cache.read(k) == v

    async def test_missing_key(self):
        cache = await self.init_cache()
        assert await cache.contains('nonexistent_key') is False
        assert await cache.read('nonexistent_key') is None

    async def test_delete(self):
        cache = await self.init_cache()
        await cache.write('do_not_delete', 'value')
        for k, v in test_data.items():
            await cache.write(k, v)

        for k in test_data.keys():
            await cache.delete(k)
            assert await cache.contains(k) is False

        assert await cache.read('do_not_delete') == 'value'

    async def test_keys_values(self):
        cache = await self.init_cache()
        assert [k async for k in cache.keys()] == []
        assert [v async for v in cache.values()] == []

        for k, v in test_data.items():
            await cache.write(k, v)

        assert {k async for k in cache.keys()} == set(test_data.keys())
        assert {v async for v in cache.values()} == set(test_data.values())

    async def test_size(self):
        cache = await self.init_cache()
        assert await cache.size() == 0
        for k, v in test_data.items():
            await cache.write(k, v)

        assert await cache.size() == len(test_data)

    async def test_clear(self):
        cache = await self.init_cache()
        for k, v in test_data.items():
            await cache.write(k, v)

        await cache.clear()
        assert await cache.size() == 0
        assert {k async for k in cache.keys()} == set()
        assert {v async for v in cache.values()} == set()
