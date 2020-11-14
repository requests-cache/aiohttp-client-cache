from collections.abc import MutableMapping
import pickle

from redis import StrictRedis

from aiohttp_client_cache.backends import PICKLE_PROTOCOL, BaseCache


class RedisCache(BaseCache):
    """Redis cache backend"""

    def __init__(self, cache_name: str, *args, connection: StrictRedis = None, **kwargs):
        super().__init__(cache_name, *args, **kwargs)
        self.responses = RedisDict(cache_name, 'responses', connection)
        self.keys_map = RedisDict(cache_name, 'urls', self.responses.connection)


class RedisDict(MutableMapping):
    """A dictionary-like interface for ``redis`` key-stores"""

    def __init__(self, namespace: str, collection_name: str, connection: StrictRedis = None):
        """
        The actual key name on the redis server will be ``namespace``:``collection_name``

        In order to deal with how redis stores data/keys, everything must be pickled.

        Args:
            namespace: namespace to use
            collection_name: name of the hash map stored in redis
            connection: Redis instance to use instead of creating a new one
        """
        self.connection = connection or StrictRedis()
        self._self_key = ':'.join([namespace, collection_name])

    def __getitem__(self, key):
        result = self.connection.hget(self._self_key, pickle.dumps(key, protocol=PICKLE_PROTOCOL))
        if result is None:
            raise KeyError
        return pickle.loads(bytes(result))

    def __setitem__(self, key, item):
        self.connection.hset(
            self._self_key,
            pickle.dumps(key, protocol=PICKLE_PROTOCOL),
            pickle.dumps(item, protocol=PICKLE_PROTOCOL),
        )

    def __delitem__(self, key):
        if not self.connection.hdel(self._self_key, pickle.dumps(key, protocol=PICKLE_PROTOCOL)):
            raise KeyError

    def __len__(self):
        return self.connection.hlen(self._self_key)

    def __iter__(self):
        for v in self.connection.hkeys(self._self_key):
            yield pickle.loads(bytes(v))

    def clear(self):
        self.connection.delete(self._self_key)

    def __str__(self):
        return str(dict(self.items()))
