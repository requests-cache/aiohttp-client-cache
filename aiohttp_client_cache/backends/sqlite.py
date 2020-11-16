import asyncio
import pickle
import sqlite3
from contextlib import asynccontextmanager

import aiosqlite

from aiohttp_client_cache.backends import PICKLE_PROTOCOL, BaseCache


class DbCache(BaseCache):
    """SQLite cache backend.

    Reading is fast, saving is a bit slower. It can store a large amount of data
    with low memory usage.
    """

    def __init__(self, cache_name: str, *args, extension: str = '.sqlite', **kwargs):
        """
        Args:
            cache_name: database filename prefix
            extension: Database file extension
        """
        super().__init__(cache_name, *args, **kwargs)
        self.responses = DbPickleDict(cache_name + extension, 'responses')
        self.keys_map = DbDict(cache_name + extension, 'urls')


class DbDict:
    """A dictionary-like object for saving large datasets to `sqlite` database

    It's possible to create multiply DbDict instances, which will be stored as separate
    tables in one database::

        d1 = DbDict('test', 'table1')
        d2 = DbDict('test', 'table2')
        d3 = DbDict('test', 'table3')

    all data will be stored in ``test.sqlite`` database into
    correspondent tables: ``table1``, ``table2`` and ``table3``
    """

    def __init__(self, filename: str, table_name: str):
        """
        Args:
            filename: filename for database (without extension)
            table_name: table name
        """
        self.filename = filename
        self.table_name = table_name

        #: Transactions can be committed if this property is set to `True`
        self.can_commit = True

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
                f'create table if not exists `{self.table_name}` (key PRIMARY KEY, value)'
            )
            self._initialized = True
        return db

    @asynccontextmanager
    async def get_connection(self, autocommit: bool = False) -> aiosqlite.Connection:
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

            >>> d1 = DbDict('test')
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

    async def read(self, key: str):
        async with self.get_connection() as db:
            cur = await db.execute(f'select value from `{self.table_name}` where key=?', (key,))
            row = await cur.fetchone()
            return row[0]

    async def read_all(self):
        async with self.get_connection() as db:
            cur = await db.execute(f'select value from `{self.table_name}`')
            return await cur.fetchall()

    async def write(self, key, item):
        async with self.get_connection(autocommit=True) as db:
            await db.execute(
                f'insert or replace into `{self.table_name}` (key,value) values (?,?)',
                (key, item),
            )

    async def delete(self, key):
        async with self.get_connection(autocommit=True) as db:
            cur = await db.execute(f'delete from `{self.table_name}` where key=?', (key,))
            if not cur.rowcount:
                raise KeyError

    async def size(self):
        with self.get_connection() as db:
            cur = await db.execute(f'select count(key) from `{self.table_name}`')
            return await cur.fetchone()[0]

    async def clear(self):
        async with self.get_connection(autocommit=True) as db:
            await db.execute(f'drop table `{self.table_name}`')
            await db.execute(f'create table `{self.table_name}` (key PRIMARY KEY, value)')
            await db.execute('vacuum')

    async def __aiter__(self):
        async with self.get_connection() as db:
            cur = await db.execute(f'select key from `{self.table_name}`')
            for row in await cur.fetchall():
                yield row[0]

    async def __anext__(self):
        pass


class DbPickleDict(DbDict):
    """ Same as :class:`DbDict`, but pickles values before saving """

    async def set(self, key, item):
        binary_item = sqlite3.Binary(pickle.dumps(item, protocol=PICKLE_PROTOCOL))
        await super().set(key, binary_item)

    async def get(self, key):
        binary_item = bytes(await super().get(key))
        return pickle.loads(binary_item)

    async def get_all(self):
        async with self.get_connection() as db:
            cur = await db.execute(f'select value from `{self.table_name}`')
            return await cur.fetchall()
