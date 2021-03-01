import pickle
from typing import Iterable

from motor.motor_asyncio import AsyncIOMotorClient

from aiohttp_client_cache.backends import BaseCache, CacheBackend, ResponseOrKey
from aiohttp_client_cache.forge_utils import extend_signature


class MongoDBBackend(CacheBackend):
    """MongoDB cache backend

    Args:
        connection: Optional client object to use instead of creating a new one

    See :py:class:`.CacheBackend` for additional args.
    """

    @extend_signature(CacheBackend.__init__)
    def __init__(
        self, cache_name: str = 'aiohttp-cache', connection: AsyncIOMotorClient = None, **kwargs
    ):
        super().__init__(cache_name=cache_name, **kwargs)
        self.responses = MongoDBPickleCache(cache_name, 'responses', connection)
        self.keys_map = MongoDBCache(cache_name, 'redirects', self.responses.connection)


class MongoDBCache(BaseCache):
    """An async-compatible interface for caching objects in MongoDB

    Args:
        db_name: database name (be careful with production databases)
        collection_name: collection name
        connection: MongoDB connection instance to use instead of creating a new one
    """

    def __init__(self, db_name, collection_name: str, connection: AsyncIOMotorClient = None):
        self.connection = connection or AsyncIOMotorClient()
        self.db = self.connection[db_name]
        self.collection = self.db[collection_name]

    async def clear(self):
        await self.collection.drop()

    async def contains(self, key: str) -> bool:
        return bool(await self.collection.find_one({'_id': key}))

    async def delete(self, key: str):
        spec = {'_id': key}
        if hasattr(self.collection, "find_one_and_delete"):
            await self.collection.find_one_and_delete(spec, {'_id': True})
        else:
            await self.collection.find_and_modify(spec, remove=True, fields={'_id': True})

    async def keys(self) -> Iterable[str]:
        return [d['_id'] for d in await self.collection.find({}, {'_id': True}).to_list(None)]

    async def read(self, key: str) -> ResponseOrKey:
        result = await self.collection.find_one({'_id': key})
        return result['data'] if result else None

    async def size(self) -> int:
        return await self.collection.count_documents({})

    async def values(self) -> Iterable[ResponseOrKey]:
        results = await self.collection.find({'data': {'$exists': True}}).to_list(None)
        return [x['data'] for x in results]

    async def write(self, key: str, item: ResponseOrKey):
        doc = {'_id': key, 'data': item}
        await self.collection.replace_one({'_id': key}, doc, upsert=True)


class MongoDBPickleCache(MongoDBCache):
    """Same as :py:class:`MongoDBCache`, but pickles values before saving"""

    async def read(self, key):
        return self.unpickle(bytes(await super().read(key)))

    async def write(self, key, item):
        await super().write(key, pickle.dumps(item, protocol=-1))
