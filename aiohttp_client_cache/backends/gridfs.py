from typing import AsyncIterable

from gridfs import GridFS
from pymongo import MongoClient

from aiohttp_client_cache.backends import BaseCache, CacheBackend, ResponseOrKey, get_valid_kwargs
from aiohttp_client_cache.backends.mongo import MongoDBCache
from aiohttp_client_cache.docs.forge_utils import extend_signature


class GridFSBackend(CacheBackend):
    """An async-compatible interface for caching objects in MongoDB GridFS.
    Use this if you need to support documents greater than 16MB.

    Args:
        connection: Optional client object to use instead of creating a new one

    See :py:class:`.CacheBackend` for additional args.
    """

    @extend_signature(CacheBackend.__init__)
    def __init__(self, cache_name: str = 'aiohttp-cache', connection: MongoClient = None, **kwargs):
        super().__init__(cache_name=cache_name, **kwargs)
        self.responses = GridFSCache(cache_name, connection, **kwargs)
        self.keys_map = MongoDBCache(cache_name, 'redirects', self.responses.connection, **kwargs)


# TODO: Incomplete/untested
# TODO: Fully async implementation. Current implementation uses blocking operations.
#   Methods are currently defined as async only for compatibility with BaseCache API.
class GridFSCache(BaseCache):
    """A dictionary-like interface for MongoDB GridFS

    Args:
        db_name: database name (be careful with production databases)
        connection: MongoDB connection instance to use instead of creating a new one
    """

    def __init__(self, db_name, connection: MongoClient = None, **kwargs):
        super().__init__(**kwargs)
        connection_kwargs = get_valid_kwargs(MongoClient.__init__, kwargs)
        self.connection = connection or MongoClient(**connection_kwargs)
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

    async def keys(self) -> AsyncIterable[str]:
        for d in self.fs.find():
            yield d._id

    async def read(self, key: str) -> ResponseOrKey:
        result = self.fs.find_one({'_id': key})
        if result is None:
            raise KeyError
        return self.deserialize(result.read())

    async def size(self) -> int:
        return self.db['fs.files'].count()

    # TODO
    async def values(self) -> AsyncIterable[ResponseOrKey]:
        if False:
            yield
        raise NotImplementedError

    async def write(self, key: str, item: ResponseOrKey):
        await self.delete(key)
        self.fs.put(self.serialize(item), **{'_id': key})
