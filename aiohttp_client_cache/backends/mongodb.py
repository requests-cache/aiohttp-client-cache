from __future__ import annotations

from collections.abc import AsyncIterable
from typing import Any

from pymongo import AsyncMongoClient

from aiohttp_client_cache.backends import BaseCache, CacheBackend, ResponseOrKey, get_valid_kwargs


class MongoDBBackend(CacheBackend):
    """Async cache backend for `MongoDB <https://www.mongodb.com>`_

    Notes:
        * Requires `pymongo <https://www.mongodb.com/docs/languages/python/pymongo-driver/current/>`_
        * Accepts keyword arguments for :py:class:`pymongo.AsyncMongoClient`

    Args:
        cache_name: Database name
        connection: Optional client object to use instead of creating a new one
        kwargs: Additional keyword arguments for :py:class:`.CacheBackend` or backend connection
    """

    def __init__(
        self,
        cache_name: str = 'aiohttp-cache',
        connection: AsyncMongoClient | None = None,
        **kwargs: Any,
    ):
        super().__init__(cache_name=cache_name, **kwargs)
        self.responses = MongoDBPickleCache(cache_name, 'responses', connection, **kwargs)
        self.redirects = MongoDBCache(cache_name, 'redirects', self.responses.connection, **kwargs)


class MongoDBCache(BaseCache):
    """An async interface for caching objects in MongoDB

    Args:
        db_name: database name (be careful with production databases)
        collection_name: collection name
        connection: MongoDB connection instance to use instead of creating a new one
        kwargs: Additional keyword args for :py:class:`~pymongo.AsyncMongoClient`
    """

    def __init__(
        self,
        db_name: str,
        collection_name: str,
        connection: AsyncMongoClient | None = None,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)

        connection_kwargs = get_valid_kwargs(
            AsyncMongoClient.__init__, kwargs, accept_varkwargs=False
        )
        self.connection = connection or AsyncMongoClient(**connection_kwargs)
        self.db = self.connection[db_name]
        self.collection = self.db[collection_name]

    async def clear(self):
        await self.collection.drop()

    async def contains(self, key: str) -> bool:
        return bool(await self.collection.find_one({'_id': key}, projection={'_id': True}))

    async def bulk_delete(self, keys: set):
        spec = {'_id': {'$in': list(keys)}}
        await self.collection.delete_many(spec)

    async def delete(self, key: str):
        await self.collection.delete_one({'_id': key})

    async def keys(self) -> AsyncIterable[str]:
        async for doc in self.collection.find({}, {'_id': True}):
            yield doc['_id']

    async def read(self, key: str) -> ResponseOrKey:
        doc = await self.collection.find_one({'_id': key}, projection={'_id': False, 'data': True})
        try:
            return doc['data']
        except TypeError:
            return None

    async def size(self) -> int:
        return await self.collection.count_documents({})

    async def values(self) -> AsyncIterable[ResponseOrKey]:
        async for doc in self.collection.find(
            {'data': {'$exists': True}}, projection={'_id': False, 'data': True}
        ):
            yield doc['data']

    async def write(self, key: str, item: ResponseOrKey):
        await self.collection.update_one({'_id': key}, {'$set': {'data': item}}, upsert=True)


class MongoDBPickleCache(MongoDBCache):
    """Same as :py:class:`MongoDBCache`, but pickles values before saving"""

    async def read(self, key):
        return self.deserialize(await super().read(key))

    async def write(self, key, item):
        await super().write(key, self.serialize(item))

    async def values(self) -> AsyncIterable[ResponseOrKey]:
        async for doc in self.collection.find({'data': {'$exists': True}}):
            yield self.deserialize(doc['data'])
