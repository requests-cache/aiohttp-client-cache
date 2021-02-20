import pickle
from typing import Iterable, Optional

from pymongo import MongoClient

from aiohttp_client_cache.backends import BaseCache, CacheBackend, ResponseOrKey
from aiohttp_client_cache.forge_utils import extend_signature


class MongoDBBackend(CacheBackend):
    """MongoDB cache backend

    Args:
        connection: Optional client object to use instead of creating a new one

    See :py:class:`.CacheBackend` for additional args.
    """

    @extend_signature(CacheBackend.__init__)
    def __init__(self, cache_name: str = 'http-cache', connection: MongoClient = None, **kwargs):
        super().__init__(cache_name=cache_name, **kwargs)
        self.responses = MongoDBPickleCache(cache_name, 'responses', connection)
        self.keys_map = MongoDBCache(cache_name, 'urls', self.responses.connection)


# TODO: Incomplete/untested
# TODO: Fully async implementation. Current implementation uses blocking operations.
#   Methods are currently defined as async only for compatibility with BaseCache API.
class MongoDBCache(BaseCache):
    """An async-compatible interface for caching objects in MongoDB

    Args:
        db_name: database name (be careful with production databases)
        collection_name: collection name
        connection: MongoDB connection instance to use instead of creating a new one
    """

    def __init__(self, db_name, collection_name: str, connection: MongoClient = None):
        self.connection = connection or MongoClient()
        self.db = self.connection[db_name]
        self.collection = self.db[collection_name]

    async def clear(self):
        self.collection.drop()

    # TODO
    async def contains(self, key: str) -> bool:
        raise NotImplementedError

    async def delete(self, key: str):
        spec = {'_id': key}
        if hasattr(self.collection, "find_one_and_delete"):
            self.collection.find_one_and_delete(spec, {'_id': True})
        else:
            self.collection.find_and_modify(spec, remove=True, fields={'_id': True})

    async def keys(self) -> Iterable[str]:
        return [d['_id'] for d in self.collection.find({}, {'_id': True})]

    async def read(self, key: str) -> Optional[ResponseOrKey]:
        result = self.collection.find_one({'_id': key})
        return result['data'] if result else None

    async def size(self) -> int:
        return self.collection.count()

    # TODO
    async def values(self) -> Iterable[ResponseOrKey]:
        raise NotImplementedError

    async def write(self, key: str, item: ResponseOrKey):
        self.collection.save({'_id': key, 'data': item})


class MongoDBPickleCache(MongoDBCache):
    """Same as :py:class:`MongoDBCache`, but pickles values before saving"""

    async def read(self, key):
        return pickle.loads(bytes(await super().read(key)))

    async def write(self, key, item):
        await super().write(key, pickle.dumps(item, protocol=-1))
