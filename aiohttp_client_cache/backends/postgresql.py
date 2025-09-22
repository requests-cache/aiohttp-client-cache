from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable
from logging import getLogger
from typing import Any

import asyncpg

from aiohttp_client_cache.backends import (
    BaseCache,
    CacheBackend,
    DictCache,
    ResponseOrKey,
    get_valid_kwargs,
)

DEFAULT_DATABASE_URL = 'postgresql://localhost/aiohttp_cache'
logger = getLogger(__name__)


class PostgresBackend(CacheBackend):
    """Async cache backend for `PostgreSQL <https://www.postgresql.org>`_

    Notes:
        * Requires `asyncpg <https://magicstack.github.io/asyncpg/>`_
        * Accepts keyword arguments for :py:func:`asyncpg.connect`

    Args:
        cache_name: Used as table name prefix
        database_url: PostgreSQL database URL
        autoclose: Close any active backend connections when the session is closed
        kwargs: Additional keyword arguments for :py:class:`.CacheBackend` or backend connection
    """

    def __init__(
        self,
        cache_name: str = 'aiohttp-cache',
        database_url: str = DEFAULT_DATABASE_URL,
        autoclose: bool = True,
        **kwargs: Any,
    ):
        super().__init__(cache_name=cache_name, autoclose=autoclose, **kwargs)
        self.responses = PostgresCache(cache_name, 'responses', database_url=database_url, **kwargs)
        self.redirects = DictCache()


class PostgresCache(BaseCache):
    """An async interface for caching pickled objects in PostgreSQL.

    Args:
        namespace: Namespace to use as table prefix
        table_name: Table name suffix
        database_url: PostgreSQL database URL
        kwargs: Additional keyword arguments for :py:func:`asyncpg.create_pool`
    """

    def __init__(
        self,
        namespace: str,
        table_name: str,
        database_url: str = DEFAULT_DATABASE_URL,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.database_url = database_url
        safe_namespace = namespace.replace('-', '_')
        self.table_name = f'{safe_namespace}_{table_name}'
        self._connection_pool: asyncpg.Pool | None = None
        self._initialized = False
        self._lock = asyncio.Lock()
        self.connection_kwargs = get_valid_kwargs(
            asyncpg.create_pool, kwargs, accept_varkwargs=False
        )

    async def get_connection_pool(self) -> asyncpg.Pool:
        """Lazy-initialize PostgreSQL connection pool"""
        async with self._lock:
            if not self._connection_pool:
                self._connection_pool = await asyncpg.create_pool(
                    self.database_url, **self.connection_kwargs
                )

            if not self._initialized:
                await self._init_db()

        return self._connection_pool

    async def _init_db(self):
        if not self._connection_pool:
            return

        async with self._connection_pool.acquire() as connection:
            await connection.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    key TEXT PRIMARY KEY,
                    value BYTEA
                )
            """)
        self._initialized = True

    async def close(self):
        self._closed = True
        if self._connection_pool:
            await self._connection_pool.close()
            self._connection_pool = None

    async def clear(self):
        pool = await self.get_connection_pool()
        async with pool.acquire() as connection:
            await connection.execute(f'DELETE FROM {self.table_name}')

    async def contains(self, key: str) -> bool:
        pool = await self.get_connection_pool()
        async with pool.acquire() as connection:
            result = await connection.fetchval(
                f'SELECT 1 FROM {self.table_name} WHERE key = $1 LIMIT 1', key
            )
            return result is not None

    async def bulk_delete(self, keys: set):
        if not keys:
            return
        pool = await self.get_connection_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                f'DELETE FROM {self.table_name} WHERE key = ANY($1)', list(keys)
            )

    async def delete(self, key: str):
        pool = await self.get_connection_pool()
        async with pool.acquire() as connection:
            await connection.execute(f'DELETE FROM {self.table_name} WHERE key = $1', key)

    async def keys(self) -> AsyncIterable[str]:
        pool = await self.get_connection_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                async for record in connection.cursor(f'SELECT key FROM {self.table_name}'):
                    yield record['key']

    async def read(self, key: str) -> ResponseOrKey:
        pool = await self.get_connection_pool()
        async with pool.acquire() as connection:
            result = await connection.fetchval(
                f'SELECT value FROM {self.table_name} WHERE key = $1', key
            )
            return self.deserialize(result) if result else None

    async def size(self) -> int:
        pool = await self.get_connection_pool()
        async with pool.acquire() as connection:
            return await connection.fetchval(f'SELECT COUNT(*) FROM {self.table_name}')

    async def values(self) -> AsyncIterable[ResponseOrKey]:
        pool = await self.get_connection_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                async for record in connection.cursor(f'SELECT value FROM {self.table_name}'):
                    yield self.deserialize(record['value'])

    async def write(self, key: str, item: ResponseOrKey):
        pool = await self.get_connection_pool()
        serialized_item = self.serialize(item)
        async with pool.acquire() as connection:
            await connection.execute(
                f'INSERT INTO {self.table_name} (key, value) VALUES ($1, $2) '
                f'ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value',
                key,
                serialized_item,
            )
