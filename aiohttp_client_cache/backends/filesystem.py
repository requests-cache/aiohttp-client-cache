from contextlib import contextmanager
from os import listdir, makedirs
from os.path import abspath, dirname, expanduser, isabs, isfile, join
from pathlib import Path
from pickle import PickleError
from shutil import rmtree
from tempfile import gettempdir
from typing import AsyncIterable, Union

import aiofiles
import aiofiles.os

from aiohttp_client_cache.backends import BaseCache, CacheBackend, ResponseOrKey
from aiohttp_client_cache.backends.sqlite import SQLiteCache


class FileBackend(CacheBackend):
    """Backend that stores cached responses as files on the local filesystem.
    Response paths will be in the format ``<cache_name>/responses/<cache_key>``.
    Redirects are stored in a SQLite database, located at ``<cache_name>/redirects.sqlite``.

    Args:
        cache_name: Base directory for cache files
        use_temp: Store cache files in a temp directory (e.g., ``/tmp/http_cache/``).
            Note: if ``cache_name`` is an absolute path, this option will be ignored.
    """

    def __init__(
        self, cache_name: Union[Path, str] = 'http_cache', use_temp: bool = False, **kwargs
    ):
        super().__init__(**kwargs)
        self.responses = FileCache(cache_name, use_temp=use_temp, **kwargs)
        db_path = join(dirname(self.responses.cache_dir), 'redirects.sqlite')
        self.redirects = SQLiteCache(db_path, 'redirects', **kwargs)


class FileCache(BaseCache):
    """A dictionary-like interface to files on the local filesystem"""

    def __init__(self, cache_name, use_temp: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.cache_dir = _get_cache_dir(cache_name, use_temp)

    @contextmanager
    def _try_io(self, ignore_errors: bool = False):
        """Attempt an I/O operation, and either ignore errors or re-raise them as KeyErrors"""
        try:
            yield
        except (IOError, OSError, PickleError) as e:
            if not ignore_errors:
                raise KeyError(e)

    def _join(self, key):
        return join(self.cache_dir, str(key))

    async def clear(self):
        """Note: Currently this is a blocking operation"""
        with self._try_io(ignore_errors=True):
            rmtree(self.cache_dir, ignore_errors=True)
            makedirs(self.cache_dir)

    async def contains(self, key: str) -> bool:
        return isfile(self._join(key))

    async def read(self, key: str) -> ResponseOrKey:
        with self._try_io():
            async with aiofiles.open(self._join(key), 'rb') as f:
                return self.deserialize(await f.read())

    async def delete(self, key: str):
        with self._try_io():
            await aiofiles.os.remove(self._join(key))

    async def write(self, key: str, value: ResponseOrKey):
        with self._try_io():
            async with aiofiles.open(self._join(key), 'wb') as f:
                await f.write(self.serialize(value) or b'')

    async def keys(self) -> AsyncIterable[str]:
        for filename in listdir(self.cache_dir):
            yield filename

    async def size(self) -> int:
        return len(listdir(self.cache_dir))

    async def values(self) -> AsyncIterable[ResponseOrKey]:
        async for key in self.keys():
            yield await self.read(key)

    async def paths(self):
        """Get file paths to all cached responses"""
        async for key in self.keys():
            yield self._join(key)


def _get_cache_dir(cache_dir: Union[Path, str], use_temp: bool) -> str:
    # Save to a temp directory, if specified
    if use_temp and not isabs(cache_dir):
        cache_dir = join(gettempdir(), cache_dir, 'responses')

    # Expand relative and user paths (~/*), and make sure parent dirs exist
    cache_dir = abspath(expanduser(str(cache_dir)))
    makedirs(cache_dir, exist_ok=True)
    return cache_dir
