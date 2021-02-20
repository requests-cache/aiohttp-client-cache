import pickle
from typing import Iterable, Optional

from redis import Redis, StrictRedis

from aiohttp_client_cache.backends import BaseCache, CacheBackend, ResponseOrKey
from aiohttp_client_cache.forge_utils import extend_signature


class RedisBackend(CacheBackend):
    """Redis cache backend.

    See :py:class:`.CacheBackend` for args.
    """

    @extend_signature(CacheBackend.__init__)
    def __init__(self, cache_name: str = 'http-cache', **kwargs):
        super().__init__(cache_name=cache_name, **kwargs)
        self.responses = RedisCache(cache_name, 'responses', **kwargs)
        self.redirects = RedisCache(cache_name, 'urls', connection=self.responses.connection)


# TODO: Incomplete/untested
# TODO: Original implementation pickled keys as well as values. Is there a reason keys need to be pickled?
# TODO: Fully async implementation. Current implementation with redis-py uses blocking operations.
#   Methods are currently defined as async only for compatibility with BaseCache API.
class RedisCache(BaseCache):
    """An async-compatible interface for caching objects in Redis.
    The actual key name on the redis server will be ``namespace:collection_name``.
    In order to deal with how redis stores data/keys, everything must be pickled.

    Args:
        namespace: namespace to use
        collection_name: name of the hash map stored in redis
        connection: An existing connection object to reuse instead of creating a new one
        kwargs: Additional keyword arguments for :py:class:`redis.Redis`

    """

    def __init__(self, namespace: str, collection_name: str, connection: Redis = None, **kwargs):
        self.connection = connection or StrictRedis(**kwargs)
        self._self_key = ':'.join([namespace, collection_name])

    @staticmethod
    def _unpickle_result(result):
        return pickle.loads(bytes(result)) if result else None

    async def clear(self):
        self.connection.delete(self._self_key)

    async def contains(self, key: str) -> bool:
        return bool(self.connection.exists(key))

    async def delete(self, key: str):
        self.connection.hdel(self._self_key, pickle.dumps(key, protocol=-1))

    async def keys(self) -> Iterable[str]:
        return [self._unpickle_result(r) for r in self.connection.hkeys(self._self_key)]

    async def read(self, key: str) -> Optional[ResponseOrKey]:
        result = self.connection.hget(self._self_key, pickle.dumps(key, protocol=-1))
        return self._unpickle_result(result)

    async def size(self) -> int:
        return self.connection.hlen(self._self_key)

    # TODO
    async def values(self) -> Iterable[ResponseOrKey]:
        raise NotImplementedError

    async def write(self, key: str, item: ResponseOrKey):
        self.connection.hset(
            self._self_key,
            pickle.dumps(key, protocol=-1),
            pickle.dumps(item, protocol=-1),
        )
