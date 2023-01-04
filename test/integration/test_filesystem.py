from contextlib import asynccontextmanager
from os.path import isfile
from shutil import rmtree
from tempfile import gettempdir
from typing import AsyncIterator

import pytest

from aiohttp_client_cache.backends.base import BaseCache
from aiohttp_client_cache.backends.filesystem import FileBackend, FileCache
from test.conftest import CACHE_NAME
from test.integration import BaseBackendTest, BaseStorageTest


class TestFileCache(BaseStorageTest):
    storage_class = FileCache
    picklable = True

    @asynccontextmanager
    async def init_cache(self, index=0, **kwargs) -> AsyncIterator[BaseCache]:
        cache = self.storage_class(f'{CACHE_NAME}_{index}', use_temp=True, **kwargs)
        await cache.clear()
        yield cache
        await cache.close()

    @classmethod
    def teardown_class(cls):
        rmtree(CACHE_NAME, ignore_errors=True)

    async def test_use_temp(self):
        relative_path = self.storage_class(CACHE_NAME).cache_dir
        temp_path = self.storage_class(CACHE_NAME, use_temp=True).cache_dir
        assert not relative_path.startswith(gettempdir())
        assert temp_path.startswith(gettempdir())

    async def test_paths(self):
        async with self.init_cache() as cache:
            for i in range(10):
                await cache.write(f'key_{i}', f'value_{i}')

            assert len([p async for p in cache.paths()]) == 10
            async for path in cache.paths():
                assert isfile(path)

    # TODO
    async def test_write_error(self):
        pass


class TestFileBackend(BaseBackendTest):
    backend_class = FileBackend
    init_kwargs = {'use_temp': True}

    @pytest.mark.skip(reason='Test not yet working for Filesystem backend')
    async def test_gather(self):
        super().test_gather()
