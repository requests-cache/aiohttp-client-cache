import asyncio
import pickle
import sqlite3
from contextlib import asynccontextmanager
from os.path import splitext
from typing import AsyncIterator, Iterable, Optional, Union

import aiosqlite

from aiohttp_client_cache.backends import BaseCache, CacheBackend, ResponseOrKey
from aiohttp_client_cache.forge_utils import extend_signature


class SQLiteBackend(CacheBackend):
    """An async SQLite cache backend.
    Reading is fast, saving is a bit slower. It can store a large amount of data
    with low memory usage.
    The path to the database file will be ``<cache_name>.sqlite``, or just ``<cache_name>`` if a
    a different file extension is specified.

    Args:
        cache_name: Database filename

    See :py:class:`.CacheBackend` for additional args.
    """

    @extend_signature(CacheBackend.__init__)
    def __init__(self, cache_name: str = 'http-cache', **kwargs):
        super().__init__(cache_name=cache_name, **kwargs)
        path, ext = splitext(cache_name)
        cache_path = f'{path}.{ext or "sqlite"}'

        self.redirects = SQLiteCache(cache_path, 'urls')
        self.responses = SQLitePickleCache(cache_path, 'responses')


class SQLiteCache(BaseCache):
    """An async interface for caching objects in a SQLite database.

    Example:

        >>> # Store data in two tables under the 'testdb' database
        >>> d1 = SQLiteCache('testdb', 'table1')
        >>> d2 = SQLiteCache('testdb', 'table2')

    Args:
        filename: filename for database (without extension)
        table_name: table name
    """

    def __init__(self, filename: str, table_name: str):
        self.filename = filename
        self.table_name = table_name
        self.can_commit = True  # Transactions can be committed if this is set to `True`

        self._bulk_commit = False
        self._initialized = False
        self._pending_connection = None
        self._lock = asyncio.Lock()

    async def _get_pending_connection(self):
        """Use/create pending connection if doing a bulk commit"""
        if not self._pending_connection:
            self._pending_connection = await aiosqlite.connect(self.filename)
        return self._pending_connection

    async def _close_pending_connection(self):
        if self._pending_connection:
            await self._pending_connection.close()
            self._pending_connection = None

    async def _init_connection(self, db: aiosqlite.Connection):
        """Create table if this is the first connection opened, and set fast save if specified"""
        await db.execute('PRAGMA synchronous = 0;')
        if not self._initialized:
            await db.execute(
                f'CREATE TABLE IF NOT EXISTS `{self.table_name}` (key PRIMARY KEY, value)'
            )
            self._initialized = True
        return db

    @asynccontextmanager
    async def get_connection(self, autocommit: bool = False) -> AsyncIterator[aiosqlite.Connection]:
        async with self._lock:
            if self._bulk_commit:
                db = await self._get_pending_connection()
            else:
                db = await aiosqlite.connect(self.filename)
            try:
                yield await self._init_connection(db)
                if autocommit and self.can_commit:
                    await db.commit()
            finally:
                if not self._bulk_commit:
                    await db.close()

    async def commit(self, force: bool = False):
        """
        Commits pending transaction if :attr:`can_commit` or `force` is `True`

        Args:
            force: force commit, ignore :attr:`can_commit`
        """
        if (force or self.can_commit) and self._pending_connection:
            await self._pending_connection.commit()

    @asynccontextmanager
    async def bulk_commit(self):
        """
        Context manager used to speedup insertion of big number of records

        Example:

            >>> d1 = SQLiteCache('test')
            >>> async with d1.bulk_commit():
            ...     for i in range(1000):
            ...         d1[i] = i * 2

        """
        self._bulk_commit = True
        self.can_commit = False
        try:
            yield
            await self.commit(force=True)
        finally:
            self._bulk_commit = False
            self.can_commit = True
            await self._close_pending_connection()

    async def clear(self):
        async with self.get_connection(autocommit=True) as db:
            await db.execute(f'DROP TABLE `{self.table_name}`')
            await db.execute(f'CREATE TABLE `{self.table_name}` (key PRIMARY KEY, value)')
            await db.execute('VACUUM')

    async def contains(self, key: str) -> bool:
        async with self.get_connection() as db:
            cur = await db.execute(f'SELECT COUNT(*) FROM `{self.table_name}` WHERE key=?', (key,))
            row = await cur.fetchone()
            return bool(row[0]) if row else False

    async def delete(self, key: str):
        async with self.get_connection(autocommit=True) as db:
            await db.execute(f'DELETE FROM `{self.table_name}` WHERE key=?', (key,))

    async def keys(self) -> Iterable[str]:
        async with self.get_connection() as db:
            cur = await db.execute(f'SELECT key FROM `{self.table_name}`')
            return [row[0] for row in await cur.fetchall()]

    async def read(self, key: str) -> Optional[ResponseOrKey]:
        async with self.get_connection() as db:
            cur = await db.execute(f'SELECT value FROM `{self.table_name}` WHERE key=?', (key,))
            row = await cur.fetchone()
            return row[0] if row else None

    async def size(self) -> int:
        async with self.get_connection() as db:
            cur = await db.execute(f'SELECT COUNT(key) FROM `{self.table_name}`')
            row = await cur.fetchone()
            return row[0] if row else 0

    async def values(self) -> Iterable[ResponseOrKey]:
        async with self.get_connection() as db:
            cur = await db.execute(f'SELECT value FROM `{self.table_name}`')
            return [row[0] for row in await cur.fetchall()]

    async def write(self, key: str, item: Union[ResponseOrKey, sqlite3.Binary]):
        async with self.get_connection(autocommit=True) as db:
            await db.execute(
                f'INSERT OR REPLACE INTO `{self.table_name}` (key,value) VALUES (?,?)',
                (key, item),
            )


class SQLitePickleCache(SQLiteCache):
    """ Same as :py:class:`SqliteCache`, but pickles values before saving """

    async def read(self, key: str) -> Optional[ResponseOrKey]:
        item = await super().read(key)
        return pickle.loads(bytes(item)) if item else None  # type: ignore

    async def values(self) -> Iterable[ResponseOrKey]:
        async with self.get_connection() as db:
            cur = await db.execute(f'select value from `{self.table_name}`')
            return [row[0] for row in await cur.fetchall()]

    async def write(self, key, item):
        binary_item = sqlite3.Binary(pickle.dumps(item, protocol=-1))
        await super().write(key, binary_item)
