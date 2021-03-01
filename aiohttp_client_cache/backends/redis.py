import pickle
from typing import Iterable

from aioredis import Redis, create_redis_pool

from aiohttp_client_cache.backends import BaseCache, CacheBackend, ResponseOrKey
from aiohttp_client_cache.forge_utils import extend_signature

DEFAULT_ADDRESS = 'redis://localhost'


class RedisBackend(CacheBackend):
    """Redis cache backend"""

    @extend_signature(CacheBackend.__init__)
    def __init__(self, cache_name: str = 'aiohttp-cache', address: str = DEFAULT_ADDRESS, **kwargs):
        super().__init__(cache_name=cache_name, **kwargs)
        self.responses = RedisCache(cache_name, 'responses', address=address, **kwargs)
        self.redirects = RedisCache(cache_name, 'redirects', address=address, **kwargs)


class RedisCache(BaseCache):
    """An async-compatible interface for caching objects in Redis.

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
        address: str = None,
        connection: Redis = None,
        **kwargs,
    ):
        self.address = address
        self._connection = connection
        self.connection_kwargs = kwargs
        self.hash_key = f'{namespace}:{collection_name}'

    async def get_connection(self):
        """Lazy-initialize redis connection"""
        if not self._connection:
            self._connection = await create_redis_pool(self.address, **self.connection_kwargs)
        return self._connection

    async def clear(self):
        connection = await self.get_connection()
        keys = await self.keys()
        if keys:
            await connection.hdel(self.hash_key, *keys)

    async def contains(self, key: str) -> bool:
        connection = await self.get_connection()
        return await connection.hexists(self.hash_key, key)

    async def delete(self, key: str):
        connection = await self.get_connection()
        await connection.hdel(self.hash_key, key)

    async def keys(self) -> Iterable[str]:
        connection = await self.get_connection()
        return [k.decode() for k in await connection.hkeys(self.hash_key)]

    async def read(self, key: str) -> ResponseOrKey:
        connection = await self.get_connection()
        result = await connection.hget(self.hash_key, key)
        return self.unpickle(result)

    async def size(self) -> int:
        connection = await self.get_connection()
        return await connection.hlen(self.hash_key)

    async def values(self) -> Iterable[ResponseOrKey]:
        connection = await self.get_connection()
        return [self.unpickle(v) for v in await connection.hvals(self.hash_key)]

    async def write(self, key: str, item: ResponseOrKey):
        connection = await self.get_connection()
        await connection.hset(
            self.hash_key,
            key,
            pickle.dumps(item, protocol=-1),
        )
