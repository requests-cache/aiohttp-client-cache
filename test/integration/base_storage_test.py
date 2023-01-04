from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator, Dict, Type

import pytest

from aiohttp_client_cache.backends.sqlite import BaseCache
from test.conftest import CACHE_NAME

pytestmark = pytest.mark.asyncio
picklable_test_data = {'key_1': 'item_1', 'key_2': datetime(2021, 8, 14), 'key_3': 3.141592654}
str_test_data = {f'key_{i}': f'item_{i}' for i in range(10)}


class BaseStorageTest:
    """Base class for testing cache storage dict-like interfaces"""

    init_kwargs: Dict = {}
    picklable: bool = False
    storage_class: Type[BaseCache] = None  # type: ignore
    test_data: Dict[str, Any] = picklable_test_data

    @asynccontextmanager
    async def init_cache(self, index=0, **kwargs) -> AsyncIterator[BaseCache]:
        self.test_data = picklable_test_data if self.picklable else str_test_data  # type: ignore
        cache = self.storage_class(CACHE_NAME, f'table_{index}', **self.init_kwargs, **kwargs)
        await cache.clear()
        yield cache
        await cache.close()

    async def test_write_read(self):
        async with self.init_cache() as cache:
            # Test write() and contains()
            for k, v in self.test_data.items():
                await cache.write(k, v)
                assert await cache.contains(k) is True

            # Test read()
            for k, v in self.test_data.items():
                assert await cache.read(k) == v

    async def test_missing_key(self):
        async with self.init_cache() as cache:
            assert await cache.contains('nonexistent_key') is False
            assert await cache.read('nonexistent_key') is None

    async def test_delete(self):
        async with self.init_cache() as cache:
            await cache.write('do_not_delete', 'value')
            for k, v in self.test_data.items():
                await cache.write(k, v)

            for k in self.test_data.keys():
                await cache.delete(k)
                assert await cache.contains(k) is False

            assert await cache.read('do_not_delete') == 'value'

    async def test_bulk_delete(self):
        async with self.init_cache() as cache:
            await cache.write('do_not_delete', 'value')
            for k, v in self.test_data.items():
                await cache.write(k, v)

            await cache.bulk_delete(self.test_data.keys())

            for k in self.test_data.keys():
                assert await cache.contains(k) is False

    async def test_bulk_delete_ignores_nonexistent_keys(self):
        async with self.init_cache() as cache:
            await cache.bulk_delete(self.test_data.keys())

    async def test_keys_values(self):
        async with self.init_cache() as cache:
            assert [k async for k in cache.keys()] == []
            assert [v async for v in cache.values()] == []

            for k, v in self.test_data.items():
                await cache.write(k, v)

            assert {k async for k in cache.keys()} == set(self.test_data.keys())
            assert {v async for v in cache.values()} == set(self.test_data.values())

    async def test_size(self):
        async with self.init_cache() as cache:
            assert await cache.size() == 0
            for k, v in self.test_data.items():
                await cache.write(k, v)

        assert await cache.size() == len(self.test_data)

    async def test_clear(self):
        async with self.init_cache() as cache:
            for k, v in self.test_data.items():
                await cache.write(k, v)

            await cache.clear()
            assert await cache.size() == 0
            assert {k async for k in cache.keys()} == set()
            assert {v async for v in cache.values()} == set()
