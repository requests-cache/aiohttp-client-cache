from __future__ import annotations

from typing import Any, AsyncIterable

from redis.asyncio import Redis, from_url

from aiohttp_client_cache.backends import BaseCache, CacheBackend, ResponseOrKey, get_valid_kwargs

DEFAULT_ADDRESS = 'redis://localhost'


class RedisBackend(CacheBackend):
    """Async cache backend for `Redis <https://redis.io>`_

    Notes:
        * Requires `redis-py <https://redis-py.readthedocs.io>`_
        * Accepts keyword arguments for :py:class:`redis.asyncio.client.Redis`

    Args:
        cache_name: Used as a namespace (prefix for hash key)
        address: Redis server URI
        kwargs: Additional keyword arguments for :py:class:`.CacheBackend` or backend connection
    """

    def __init__(
        self, cache_name: str = 'aiohttp-cache', address: str = DEFAULT_ADDRESS, **kwargs: Any
    ):
        super().__init__(cache_name=cache_name, **kwargs)
        self.responses = RedisCache(cache_name, 'responses', address=address, **kwargs)
        self.redirects = RedisCache(cache_name, 'redirects', address=address, **kwargs)


class RedisCache(BaseCache):
    """An async interface for caching objects in Redis.

    Args:
        namespace: namespace to use
        collection_name: name of the hash map stored in redis
        connection: An existing connection object to reuse instead of creating a new one
        address: Address of Redis server
        kwargs: Additional keyword arguments for :py:class:`aioredis.Redis`

    Note: The hash key name on the redis server will be ``namespace:collection_name``.
    """

    def __init__(
        self,
        namespace: str,
        collection_name: str,
        address: str = DEFAULT_ADDRESS,
        connection: Redis | None = None,
        **kwargs: Any,
    ):
        # Pop off BaseCache kwargs and use the rest as Redis connection kwargs
        super().__init__(**kwargs)
        self.address = address
        self._connection = connection
        self.connection_kwargs = get_valid_kwargs(Redis.__init__, kwargs)
        self.hash_key = f'{namespace}:{collection_name}'

    async def get_connection(self):
        """Lazy-initialize redis connection"""
        if not self._connection:
            self._connection = await from_url(self.address, **self.connection_kwargs)
        return self._connection

    async def close(self):
        if self._connection:
            await self._connection.aclose()  # type: ignore[attr-defined]
            self._connection = None

    async def clear(self):
        connection = await self.get_connection()
        async for key in self.keys():
            await connection.hdel(self.hash_key, key)

    async def contains(self, key: str) -> bool:
        connection = await self.get_connection()
        return await connection.hexists(self.hash_key, key)

    async def bulk_delete(self, keys: set):
        """Requires redis version >=2.4"""
        connection = await self.get_connection()
        await connection.hdel(self.hash_key, *keys)

    async def delete(self, key: str):
        connection = await self.get_connection()
        await connection.hdel(self.hash_key, key)

    async def keys(self) -> AsyncIterable[str]:
        connection = await self.get_connection()
        for k in await connection.hkeys(self.hash_key):
            yield k.decode()

    async def read(self, key: str) -> ResponseOrKey:
        connection = await self.get_connection()
        result = await connection.hget(self.hash_key, key)
        return self.deserialize(result)

    async def size(self) -> int:
        connection = await self.get_connection()
        return await connection.hlen(self.hash_key)

    async def values(self) -> AsyncIterable[ResponseOrKey]:
        connection = await self.get_connection()
        for v in await connection.hvals(self.hash_key):
            yield self.deserialize(v)

    async def write(self, key: str, item: ResponseOrKey):
        connection = await self.get_connection()
        await connection.hset(
            self.hash_key,
            key,
            self.serialize(item),
        )
