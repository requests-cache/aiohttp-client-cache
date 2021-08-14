import os
from sys import version_info
from tempfile import gettempdir
from unittest.mock import patch

import pytest

from aiohttp_client_cache.backends.sqlite import SQLiteBackend, SQLiteCache, SQLitePickleCache
from test.conftest import CACHE_NAME
from test.integration import BaseBackendTest, BaseStorageTest

pytestmark = pytest.mark.asyncio
skip_37 = pytest.mark.skipif(
    version_info < (3, 8), reason='Test requires AsyncMock from python 3.8+'
)


class TestSQLiteCache(BaseStorageTest):
    init_kwargs = {'use_temp': True}
    storage_class = SQLiteCache

    @classmethod
    def teardown_class(cls):
        try:
            os.unlink(f'{CACHE_NAME}.sqlite')
        except Exception:
            pass

    def test_use_temp(self):
        relative_path = self.storage_class(CACHE_NAME).filename
        temp_path = self.storage_class(CACHE_NAME, use_temp=True).filename
        assert not relative_path.startswith(gettempdir())
        assert temp_path.startswith(gettempdir())

    async def test_bulk_commit(self):
        cache = await self.init_cache()
        async with cache.bulk_commit():
            pass

        n_items = 1000
        async with cache.bulk_commit():
            for i in range(n_items):
                await cache.write(f'key_{i}', f'value_{i}')

        keys = {k async for k in cache.keys()}
        values = {v async for v in cache.values()}
        assert keys == {f'key_{i}' for i in range(n_items)}
        assert values == {f'value_{i}' for i in range(n_items)}

    async def test_fast_save(self):
        cache_1 = await self.init_cache(index=1, fast_save=True)
        cache_2 = await self.init_cache(index=2, fast_save=True)

        n = 1000
        for i in range(n):
            await cache_1.write(i, i)
            await cache_2.write(i, i)

        keys_1 = {k async for k in cache_1.keys()}
        keys_2 = {k async for k in cache_2.keys()}
        values_1 = {v async for v in cache_1.values()}
        values_2 = {v async for v in cache_2.values()}
        assert keys_1 == keys_2 == set(range(n))
        assert values_1 == values_2 == set(range(n))

    @skip_37
    @patch('aiohttp_client_cache.backends.sqlite.aiosqlite')
    async def test_connection_kwargs(self, mock_sqlite):
        """A spot check to make sure optional connection kwargs gets passed to connection"""
        from unittest.mock import AsyncMock

        mock_sqlite.connect = AsyncMock()
        cache = await self.init_cache(timeout=0.5, invalid_kwarg='???')
        mock_sqlite.connect.assert_called_with(cache.filename, timeout=0.5)

    # TODO: Tests for unimplemented features
    # async def test_chunked_bulk_delete(self):
    #     """When deleting more items than SQLite can handle in a single statement, it should be
    #     chunked into multiple smaller statements
    #     """
    #     # Populate the cache with more items than can fit in a single delete statement
    #     cache = await self.init_cache()
    #     async with cache.bulk_commit():
    #         for i in range(2000):
    #             await cache.write(f'key_{i}', f'value_{i}')

    #     keys = {k async for k in cache.keys()}

    #     # First pass to ensure that bulk_delete is split across three statements
    #     with patch.object(cache, 'connection') as mock_connection:
    #         con = mock_connection().__enter__.return_value
    #         cache.bulk_delete(keys)
    #         assert con.execute.call_count == 3

    #     # Second pass to actually delete keys and make sure it doesn't explode
    #     await cache.bulk_delete(keys)
    #     assert await cache.size() == 0

    # async def test_noop(self):
    #     async def do_noop_bulk(cache):
    #         async with cache.bulk_commit():
    #             pass
    #         del cache

    #     cache = await self.init_cache()
    #     thread = Thread(target=do_noop_bulk, args=(cache,))
    #     thread.start()
    #     thread.join()

    #     # make sure connection is not closed by the thread
    #     await cache.write('key_1', 'value_1')
    #     assert {k async for k in cache.keys()} == {'key_1'}


class TestSQLitePickleCache(BaseStorageTest):
    picklable = True
    storage_class = SQLitePickleCache


class TestSQLiteBackend(BaseBackendTest):
    backend_class = SQLiteBackend
    init_kwargs = {'use_temp': True}
