from typing import AsyncIterable

from motor.motor_asyncio import AsyncIOMotorClient

from aiohttp_client_cache.backends import BaseCache, CacheBackend, ResponseOrKey, get_valid_kwargs
from aiohttp_client_cache.docs import extend_init_signature, mongo_template


@extend_init_signature(CacheBackend, mongo_template)
class MongoDBBackend(CacheBackend):
    """Async cache backend for `MongoDB <https://www.mongodb.com>`_
    (requires `motor <https://motor.readthedocs.io>`_)
    """

    def __init__(
        self, cache_name: str = 'aiohttp-cache', connection: AsyncIOMotorClient = None, **kwargs
    ):
        """
        Args:
            cache_name: Database name
            connection: Optional client object to use instead of creating a new one
        """
        super().__init__(cache_name=cache_name, **kwargs)
        self.responses = MongoDBPickleCache(cache_name, 'responses', connection, **kwargs)
        self.redirects = MongoDBCache(cache_name, 'redirects', self.responses.connection, **kwargs)


class MongoDBCache(BaseCache):
    """An async interface for caching objects in MongoDB

    Args:
        db_name: database name (be careful with production databases)
        collection_name: collection name
        connection: MongoDB connection instance to use instead of creating a new one
        kwargs: Additional keyword args for :py:class:`~motor.motor_asyncio.AsyncIOMotorClient`
    """

    def __init__(
        self, db_name: str, collection_name: str, connection: AsyncIOMotorClient = None, **kwargs
    ):
        super().__init__(**kwargs)
        connection_kwargs = get_valid_kwargs(AsyncIOMotorClient.__init__, kwargs)
        self.connection = connection or AsyncIOMotorClient(**connection_kwargs)
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

    async def keys(self) -> AsyncIterable[str]:
        async for doc in self.collection.find({}, {'_id': True}):
            yield doc['_id']

    async def read(self, key: str) -> ResponseOrKey:
        result = await self.collection.find_one({'_id': key})
        return result['data'] if result else None

    async def size(self) -> int:
        return await self.collection.count_documents({})

    async def values(self) -> AsyncIterable[ResponseOrKey]:
        async for doc in self.collection.find({'data': {'$exists': True}}):
            yield doc['data']

    async def write(self, key: str, item: ResponseOrKey):
        doc = {'_id': key, 'data': item}
        await self.collection.replace_one({'_id': key}, doc, upsert=True)


class MongoDBPickleCache(MongoDBCache):
    """Same as :py:class:`MongoDBCache`, but pickles values before saving"""

    async def read(self, key):
        return self.deserialize(await super().read(key))

    async def write(self, key, item):
        await super().write(key, self.serialize(item))

    async def values(self) -> AsyncIterable[ResponseOrKey]:
        async for doc in self.collection.find({'data': {'$exists': True}}):
            yield self.deserialize(doc['data'])
