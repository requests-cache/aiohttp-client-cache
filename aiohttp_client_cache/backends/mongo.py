import pickle
from typing import Iterable, Optional

from pymongo import MongoClient

from aiohttp_client_cache.backends import BaseCache, CacheController, ResponseOrKey


class MongoDBController(CacheController):
    """MongoDB cache backend"""

    def __init__(self, cache_name: str, *args, connection: MongoClient = None, **kwargs):
        super().__init__(cache_name, *args, **kwargs)
        self.responses = MongoDBPickleCache(cache_name, 'responses', connection)
        self.keys_map = MongoDBCache(cache_name, 'urls', self.responses.connection)


# TODO: Incomplete/untested
class MongoDBCache(BaseCache):
    """A dictionary-like interface for ``mongo`` database"""

    def __init__(self, db_name, collection_name: str, connection: MongoClient = None):
        """
        Args:
            db_name: database name (be careful with production databases)
            collection_name: collection name
            connection: MongoDB connection instance to use instead of creating a new one
        """
        self.connection = connection or MongoClient()
        self.db = self.connection[db_name]
        self.collection = self.db[collection_name]

    async def read(self, key: str) -> Optional[ResponseOrKey]:
        result = self.collection.find_one({'_id': key})
        return result['data'] if result else None

    # TODO
    async def read_all(self) -> Iterable[ResponseOrKey]:
        raise NotImplementedError

    async def keys(self) -> Iterable[str]:
        return [d['_id'] for d in self.collection.find({}, {'_id': True})]

    async def write(self, key: str, item: ResponseOrKey):
        self.collection.save({'_id': key, 'data': item})

    async def delete(self, key: str):
        spec = {'_id': key}
        if hasattr(self.collection, "find_one_and_delete"):
            self.collection.find_one_and_delete(spec, {'_id': True})
        else:
            self.collection.find_and_modify(spec, remove=True, fields={'_id': True})

    # TODO
    async def contains(self, key: str) -> bool:
        raise NotImplementedError

    async def size(self) -> int:
        return self.collection.count()

    async def clear(self):
        self.collection.drop()


class MongoDBPickleCache(MongoDBCache):
    """Same as :py:class:`MongoDBCache`, but pickles values before saving"""

    async def read(self, key):
        return pickle.loads(bytes(await super().read(key)))

    async def write(self, key, item):
        await super().write(key, pickle.dumps(item, protocol=-1))
