from __future__ import annotations
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator, TypeVar

import pytest

from aiohttp_client_cache.backends.sqlite import BaseCache
from test.conftest import CACHE_NAME

pytestmark = pytest.mark.asyncio
picklable_test_data = {'key_1': 'item_1', 'key_2': datetime(2021, 8, 14), 'key_3': 3.141592654}
str_test_data = {f'key_{i}': f'item_{i}' for i in range(10)}

BaseCacheT = TypeVar('BaseCacheT', bound=BaseCache)


class BaseStorageTest:
    """Base class for testing cache storage dict-like interfaces"""

    init_kwargs: dict = {}
    picklable: bool = False
    test_data: dict[str, Any] = picklable_test_data
    storage_class: type[BaseCache]

    @asynccontextmanager
    async def init_cache(
        self, storage_class: type[BaseCacheT] | None = None, index=0, **kwargs
    ) -> AsyncIterator[BaseCacheT]:
        self.test_data = picklable_test_data if self.picklable else str_test_data  # type: ignore
        cache_class = storage_class or self.storage_class
        assert cache_class
        cache = cache_class(CACHE_NAME, f'table_{index}', **self.init_kwargs, **kwargs)
        await cache.clear()
        yield cache  # type: ignore[misc]
        await cache.close()

    async def test_write_read(self):
        async with self.init_cache() as cache:  # type: ignore[var-annotated]
            # Test write(), contains(), and size()
            for k, v in self.test_data.items():
                await cache.write(k, v)
                assert await cache.contains(k) is True
            assert await cache.size() == len(self.test_data)

            # Test read()
            for k, v in self.test_data.items():
                assert await cache.read(k) == v

    async def test_missing_key(self):
        async with self.init_cache() as cache:  # type: ignore[var-annotated]
            assert await cache.contains('nonexistent_key') is False
            assert await cache.read('nonexistent_key') is None

    async def test_delete(self):
        async with self.init_cache() as cache:  # type: ignore[var-annotated]
            await cache.write('do_not_delete', 'value')
            for k, v in self.test_data.items():
                await cache.write(k, v)

            for k in self.test_data.keys():
                await cache.delete(k)
                assert await cache.contains(k) is False

            assert await cache.read('do_not_delete') == 'value'

    async def test_bulk_delete(self):
        async with self.init_cache() as cache:  # type: ignore[var-annotated]
            await cache.write('do_not_delete', 'value')
            for k, v in self.test_data.items():
                await cache.write(k, v)

            await cache.bulk_delete(self.test_data.keys())

            for k in self.test_data.keys():
                assert await cache.contains(k) is False

    async def test_bulk_delete_ignores_nonexistent_keys(self):
        async with self.init_cache() as cache:  # type: ignore[var-annotated]
            await cache.bulk_delete(self.test_data.keys())

    async def test_keys_values(self):
        test_data = {f'key_{i}': f'value_{i}' for i in range(20)}

        # test keys() and values()
        async with self.init_cache() as cache:  # type: ignore[var-annotated]
            assert [k async for k in cache.keys()] == []
            assert [v async for v in cache.values()] == []

            for k, v in test_data.items():
                await cache.write(k, v)

            assert sorted([k async for k in cache.keys()]) == sorted(test_data.keys())
            assert sorted([v async for v in cache.values()]) == sorted(test_data.values())

    async def test_size(self):
        async with self.init_cache() as cache:  # type: ignore[var-annotated]
            assert await cache.size() == 0
            for k, v in self.test_data.items():
                await cache.write(k, v)

            assert await cache.size() == len(self.test_data)

    async def test_clear(self):
        async with self.init_cache() as cache:  # type: ignore[var-annotated]
            for k, v in self.test_data.items():
                await cache.write(k, v)

            await cache.clear()
            assert await cache.size() == 0
            assert {k async for k in cache.keys()} == set()
            assert {v async for v in cache.values()} == set()
