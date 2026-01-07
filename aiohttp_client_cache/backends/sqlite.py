from __future__ import annotations

import asyncio
import functools
import sqlite3
import warnings
from collections.abc import AsyncIterable, AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from logging import getLogger
from os import makedirs
from os.path import abspath, basename, dirname, expanduser, isabs, join
from pathlib import Path
from tempfile import gettempdir
from typing import Any

import aiosqlite

from aiohttp_client_cache.backends import BaseCache, CacheBackend, ResponseOrKey, get_valid_kwargs

bulk_commit_var: ContextVar[bool] = ContextVar('bulk_commit', default=False)
logger = getLogger(__name__)


closed_session_warning = functools.partial(
    warnings.warn,
    'Cache access after closing the `Cachedsession` context manager '
    + 'is discouraged and can be forbidden in the future to prevent '
    + 'errors related to a closed database connection. Use `autoclose=False` '
    + 'if you are managing the cache backend connection on your side or '
    + 'reusing a single cache class instance in multiple `CachedSession`.',
    stacklevel=2,
)


class SQLiteBackend(CacheBackend):
    """Async cache backend for `SQLite <https://www.sqlite.org>`_

    Notes:
        * Requires `aiosqlite <https://aiosqlite.omnilib.dev>`_
        * Accepts keyword arguments for :py:func:`sqlite3.connect` / :py:func:`aiosqlite.connect`
        * The path to the database file will be ``<cache_name>`` (or ``<cache_name>.sqlite`` if no
          file extension is specified)

    Args:
        cache_name: Database filename
        use_temp: Store database in a temp directory (e.g., ``/tmp/http_cache.sqlite``).
            Note: if ``cache_name`` is an absolute path, this option will be ignored.
        fast_save: Increase cache write performance, but with the possibility of data loss. See
            `pragma: synchronous <http://www.sqlite.org/pragma.html#pragma_synchronous>`_ for
            details.
        autoclose: Close any active backend connections when the session is closed
        kwargs: Additional keyword arguments for :py:class:`.CacheBackend` or backend connection
    """

    def __init__(
        self,
        cache_name: str = 'aiohttp-cache',
        use_temp: bool = False,
        fast_save: bool = False,
        autoclose: bool = True,
        **kwargs: Any,
    ):
        super().__init__(cache_name=cache_name, autoclose=autoclose, **kwargs)
        self.responses = SQLitePickleCache(
            cache_name, 'responses', use_temp=use_temp, fast_save=fast_save, **kwargs
        )
        self.redirects = SQLiteCache(
            cache_name,
            'redirects',
            use_temp=use_temp,
            connection=self.responses._connection,
            lock=self.responses._lock,
            **kwargs,
        )


class SQLiteCache(BaseCache):
    """An async interface for caching objects in a SQLite database.

    Example:

        >>> # Store data in two tables under the 'testdb' database
        >>> d1 = SQLiteCache('testdb', 'table1')
        >>> d2 = SQLiteCache('testdb', 'table2')

    Args:
        filename: Database filename
        table_name: Table name
        use_temp: Store database in a temp directory (e.g., ``/tmp/http_cache.sqlite``).
            Note: if ``cache_name`` is an absolute path, this option will be ignored.
        connection: Existing aiosqlite connection to reuse
        lock: Existing async lock to reuse
        kwargs: Additional keyword arguments for :py:func:`sqlite3.connect`
    """

    def __init__(
        self,
        filename: str,
        table_name: str = 'aiohttp-cache',
        use_temp: bool = False,
        fast_save: bool = False,
        connection: aiosqlite.Connection | None = None,
        lock: asyncio.Lock | None = None,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.fast_save = fast_save
        self.filename = _get_cache_filename(filename, use_temp)
        self.table_name = table_name

        # Create a connection object, but delay actually connecting until the first request
        connection_kwargs = get_valid_kwargs(sqlite_template, kwargs)
        self._connection = connection or aiosqlite.connect(self.filename, **connection_kwargs)
        self._lock = lock or asyncio.Lock()
        self._initialized = False

    @asynccontextmanager
    async def get_connection(self, commit: bool = False) -> AsyncIterator[aiosqlite.Connection]:
        """Wrapper around aiosqlite connection to ensure it and the database are initialized"""
        # Note: aiosqlite.Connection is a Thread subclass. Awaiting it will start the thread,
        # set an internal _connection attribute (sqlite3.Connection), and return itself.
        # Doing this here delays the actual connection until the first request, and allows sharing
        # the connection object between multiple SQLiteCache instances.
        async with self._lock:
            if self._connection._connection is None:
                self._connection = await self._connection
            # If reusing an existing connection, database may not be initialized yet
            if not self._initialized:
                await self._init_db()

        yield self._connection

        if self._closed:
            closed_session_warning()
        if commit and not bulk_commit_var.get():
            await self._connection.commit()

    async def _init_db(self):
        """Initialize the database, if it hasn't already been"""
        if self.fast_save:
            await self._connection.execute('PRAGMA synchronous = 0;')
        await self._connection.execute(
            f'CREATE TABLE IF NOT EXISTS `{self.table_name}` (key PRIMARY KEY, value)'
        )
        self._initialized = True

    def __del__(self):
        """If the aiosqlite connection is still open when this object is deleted, force its thread
        to close by stopping its internal queue. This is basically a last resort to avoid hanging
        the application if this backend is used without the CachedSession contextmanager.
        """
        if self._connection is not None:
            try:
                # aiosqlite >= 0.22.1
                if hasattr(self._connection, 'stop'):
                    self._connection.stop()
                # aiosqlite <= 0.22.0
                else:
                    self._connection._stop_running()
            except (AttributeError, TypeError):
                logger.warning('Could not close SQLite connection thread', exc_info=True)
            self._connection = None

    @asynccontextmanager
    async def bulk_commit(self):
        """Contextmanager to more efficiently write a large number of records at once

        Example:

            >>> cache = SQLiteCache('test')
            >>> async with cache.bulk_commit():
            ...     for i in range(1000):
            ...         await cache.write(f'key_{i}', str(i))

        """
        bulk_commit_var.set(True)
        try:
            yield
            await self._connection.commit()
        finally:
            bulk_commit_var.set(False)

    async def clear(self):
        async with self.get_connection(commit=True) as db, self._lock:
            await db.execute(f'DROP TABLE `{self.table_name}`')
            await db.execute('VACUUM')
            await self._init_db()

    async def close(self):
        """Close any open connections"""
        self._closed = True
        async with self._lock:
            if self._connection is not None:
                await self._connection.close()
                self._connection = None

    async def contains(self, key: str) -> bool:
        async with self.get_connection() as db:
            cursor = await db.execute(
                f'SELECT COUNT(*) FROM `{self.table_name}` WHERE key=?', (key,)
            )
            row = await cursor.fetchone()
            return bool(row[0]) if row else False

    async def bulk_delete(self, keys: set):
        async with self.get_connection(commit=True) as db:
            placeholders = ', '.join('?' for _ in keys)
            await db.execute(
                f'DELETE FROM `{self.table_name}` WHERE key IN ({placeholders})',
                tuple(keys),
            )

    async def delete(self, key: str):
        async with self.get_connection(commit=True) as db:
            await db.execute(f'DELETE FROM `{self.table_name}` WHERE key=?', (key,))

    async def keys(self) -> AsyncIterable[str]:
        async with self.get_connection() as db:
            async with db.execute(f'SELECT key FROM `{self.table_name}`') as cursor:
                async for row in cursor:
                    yield row[0]

    async def read(self, key: str) -> ResponseOrKey:
        async with self.get_connection() as db:
            if self._closed:
                closed_session_warning()
            cursor = await db.execute(f'SELECT value FROM `{self.table_name}` WHERE key=?', (key,))
            row = await cursor.fetchone()
            return row[0] if row else None

    async def size(self) -> int:
        async with self.get_connection() as db:
            cursor = await db.execute(f'SELECT COUNT(key) FROM `{self.table_name}`')
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def values(self) -> AsyncIterable[ResponseOrKey]:
        async with self.get_connection() as db:
            async with db.execute(f'SELECT value FROM `{self.table_name}`') as cursor:
                async for row in cursor:
                    yield row[0]

    async def write(self, key: str, item: ResponseOrKey | sqlite3.Binary):
        async with self.get_connection(commit=True) as db:
            await db.execute(
                f'INSERT OR REPLACE INTO `{self.table_name}` (key,value) VALUES (?,?)',
                (key, item),
            )


class SQLitePickleCache(SQLiteCache):
    """Same as :py:class:`SqliteCache`, but pickles values before saving"""

    async def read(self, key: str) -> ResponseOrKey:
        return self.deserialize(await super().read(key))

    async def values(self) -> AsyncIterable[ResponseOrKey]:
        async with self.get_connection() as db:
            async with db.execute(f'select value from `{self.table_name}`') as cursor:
                async for row in cursor:
                    yield self.deserialize(row[0])

    async def write(self, key, item):
        await super().write(key, sqlite3.Binary(self.serialize(item)))  # type: ignore[arg-type]


def sqlite_template(
    timeout: float = 5.0,
    detect_types: int = 0,
    isolation_level: str | None = None,
    check_same_thread: bool = True,
    factory: type | None = None,
    cached_statements: int = 100,
    uri: bool = False,
):
    """Template function to get an accurate function signature for :py:func:`sqlite3.connect`"""


def _get_cache_filename(filename: Path | str, use_temp: bool) -> str:
    """Get resolved path for database file"""
    # Save to a temp directory, if specified
    if use_temp and not isabs(filename):
        filename = join(gettempdir(), filename)

    # Expand relative and user paths (~/*), and add file extension if not specified
    filename = abspath(expanduser(str(filename)))
    if '.' not in basename(filename):
        filename += '.sqlite'

    # Make sure parent dirs exist
    makedirs(dirname(filename), exist_ok=True)
    return filename
