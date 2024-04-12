from __future__ import annotations
import asyncio
import os
from contextlib import asynccontextmanager
from tempfile import gettempdir
from unittest.mock import MagicMock, patch

import pytest

import aiosqlite
from aiohttp_client_cache.backends.sqlite import (
    SQLiteBackend,
    SQLiteCache,
    SQLitePickleCache,
)
from test.conftest import CACHE_NAME, httpbin
from test.integration import BaseBackendTest, BaseStorageTest

pytestmark = pytest.mark.asyncio


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
        async with self.init_cache(self.storage_class) as cache:
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

    @patch('aiohttp_client_cache.backends.sqlite.aiosqlite')
    async def test_concurrent_bulk_commit(self, mock_sqlite):
        """Multiple concurrent bulk commits should not interfere with each other"""
        from unittest.mock import AsyncMock

        mock_connection = AsyncMock()
        mock_sqlite.connect = AsyncMock(return_value=mock_connection)

        @asynccontextmanager
        async def bulk_commit_ctx():
            async with self.init_cache(self.storage_class) as cache:

                async def bulk_commit_items(n_items):
                    async with cache.bulk_commit():
                        for i in range(n_items):
                            await cache.write(f'key_{n_items}_{i}', f'value_{i}')

                yield bulk_commit_items

        async with bulk_commit_ctx() as bulk_commit_items:
            assert mock_connection.commit.call_count == 1
            tasks = [asyncio.create_task(bulk_commit_items(n)) for n in [10, 100, 1000, 10000]]
            await asyncio.gather(*tasks)
            assert mock_connection.commit.call_count == 5

    async def test_fast_save(self):
        async with self.init_cache(
            self.storage_class, index=1, fast_save=True
        ) as cache_1, self.init_cache(self.storage_class, index=2, fast_save=True) as cache_2:
            for i in range(1000):
                await cache_1.write(i, i)  # type: ignore[arg-type]
                await cache_2.write(i, i)  # type: ignore[arg-type]

            keys_1 = {k async for k in cache_1.keys()}
            keys_2 = {k async for k in cache_2.keys()}
            values_1 = {v async for v in cache_1.values()}
            values_2 = {v async for v in cache_2.values()}
            assert keys_1 == keys_2 == set(range(1000))
            assert values_1 == values_2 == set(range(1000))

    @patch('aiohttp_client_cache.backends.sqlite.aiosqlite')
    async def test_connection_kwargs(self, mock_sqlite):
        """A spot check to make sure optional connection kwargs gets passed to connection"""
        from unittest.mock import AsyncMock

        mock_sqlite.connect = AsyncMock()
        async with self.init_cache(self.storage_class, timeout=0.5, invalid_kwarg='???') as cache:
            mock_sqlite.connect.assert_called_with(cache.filename, timeout=0.5)

    async def test_close(self):
        async with self.init_cache(self.storage_class) as cache:
            async with cache.get_connection():
                pass
            await cache.close()
            await cache.close()  # Closing again should be a no-op
            assert cache._connection is None

    async def test_failed_thread_close(self):
        """If closing the connection thread fails, it should log a warning and continue"""
        async with self.init_cache(self.storage_class) as cache:
            async with cache.get_connection():
                pass
            with patch.object(aiosqlite.Connection, '_stop_running', side_effect=AttributeError):
                del cache

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
    init_kwargs = {'use_temp': True}
    picklable = True
    storage_class = SQLitePickleCache


class TestSQLiteBackend(BaseBackendTest):
    backend_class = SQLiteBackend
    init_kwargs = {'use_temp': True}

    async def test_autoclose__default(self):
        """By default, the backend should be closed when the session is closed"""

        async with self.init_session() as session:
            mock_close = MagicMock(wraps=session.cache.close)
            session.cache.close = mock_close  # type: ignore[method-assign]

            await session.get(httpbin('get'))
        mock_close.assert_called_once()
