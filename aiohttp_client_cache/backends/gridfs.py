import pickle
from typing import Iterable, Optional

from gridfs import GridFS
from pymongo import MongoClient

from aiohttp_client_cache.backends import BaseCache, CacheController, ResponseOrKey
from aiohttp_client_cache.backends.mongo import MongoDBCache


class GridFSController(CacheController):
    """An async-compatible interface for caching objects in MongoDB GridFS.
    Use this if you need to support documents greater than 16MB.
    """

    def __init__(self, cache_name: str, *args, connection: MongoClient = None, **kwargs):
        super().__init__(cache_name, *args, **kwargs)
        self.responses = GridFSCache(cache_name, connection)
        self.keys_map = MongoDBCache(cache_name, 'http_redirects', self.responses.connection)


# TODO: Incomplete/untested
# TODO: Fully async implementation. Current implementation uses blocking operations.
#   Methods are currently defined as async only for compatibility with BaseCache API.
class GridFSCache(BaseCache):
    """A dictionary-like interface for MongoDB GridFS

    Args:
        db_name: database name (be careful with production databases)
        connection: MongoDB connection instance to use instead of creating a new one
    """

    def __init__(self, db_name, connection: MongoClient = None):
        self.connection = connection or MongoClient()
        self.db = self.connection[db_name]
        self.fs = GridFS(self.db)

    # TODO
    async def contains(self, key: str) -> bool:
        raise NotImplementedError

    async def clear(self):
        self.db['fs.files'].drop()
        self.db['fs.chunks'].drop()

    async def delete(self, key: str):
        res = self.fs.find_one({'_id': key})
        if res is not None:
            self.fs.delete(res._id)

    async def keys(self) -> Iterable[str]:
        return [d._id for d in self.fs.find()]

    async def read(self, key: str) -> Optional[ResponseOrKey]:
        result = self.fs.find_one({'_id': key})
        if result is None:
            raise KeyError
        return pickle.loads(bytes(result.read()))

    async def size(self) -> int:
        return self.db['fs.files'].count()

    # TODO
    async def values(self) -> Iterable[ResponseOrKey]:
        raise NotImplementedError

    async def write(self, key: str, item: ResponseOrKey):
        await self.delete(key)
        self.fs.put(pickle.dumps(item, protocol=-1), **{'_id': key})
