from typing import AsyncIterable

from aioredis import Redis, create_redis_pool

from aiohttp_client_cache.backends import BaseCache, CacheBackend, ResponseOrKey, get_valid_kwargs
from aiohttp_client_cache.docs import extend_init_signature, redis_template

DEFAULT_ADDRESS = 'redis://localhost'


@extend_init_signature(CacheBackend, redis_template)
class RedisBackend(CacheBackend):
    """Async cache backend for `Redis <https://redis.io>`_
    (requires `aioredis <https://aioredis.readthedocs.io>`_)
    """

    def __init__(self, cache_name: str = 'aiohttp-cache', address: str = DEFAULT_ADDRESS, **kwargs):
        super().__init__(cache_name=cache_name, **kwargs)
        self.responses = RedisCache(cache_name, 'responses', address=address, **kwargs)
        self.redirects = RedisCache(cache_name, 'redirects', address=address, **kwargs)

    async def close(self):
        """Close any active connections"""
        await self.responses.close()
        await self.redirects.close()


class RedisCache(BaseCache):
    """An async interface for caching objects in Redis.

    Args:
        namespace: namespace to use
        collection_name: name of the hash map stored in redis
        connection: An existing connection object to reuse instead of creating a new one
        address: Address of Redis server
        kwargs: Additional keyword arguments for :py:class:`redis.Redis`

    Note: The hash key name on the redis server will be ``namespace:collection_name``.
    """

    def __init__(
        self,
        namespace: str,
        collection_name: str,
        address: str = DEFAULT_ADDRESS,
        connection: Redis = None,
        **kwargs,
    ):
        # Pop off BaseCache kwargs and use the rest as Redis connection kwargs
        super().__init__(**kwargs)
        self.address = address
        self._connection = connection
        self.connection_kwargs = get_valid_kwargs(create_redis_pool, kwargs)
        self.hash_key = f'{namespace}:{collection_name}'

    async def get_connection(self):
        """Lazy-initialize redis connection"""
        if not self._connection:
            self._connection = await create_redis_pool(self.address, **self.connection_kwargs)
        return self._connection

    async def close(self):
        if self._connection:
            self._connection.close()
            await self._connection.wait_closed()
            self._connection = None

    async def clear(self):
        connection = await self.get_connection()
        async for key in self.keys():
            await connection.hdel(self.hash_key, key)

    async def contains(self, key: str) -> bool:
        connection = await self.get_connection()
        return await connection.hexists(self.hash_key, key)

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
