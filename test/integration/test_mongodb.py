from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from pymongo import AsyncMongoClient, MongoClient
from pymongo.errors import ConnectionFailure

from aiohttp_client_cache.backends.mongodb import MongoDBBackend, MongoDBCache, MongoDBPickleCache
from test.integration import BaseBackendTest, BaseStorageTest


def is_db_running():
    """Test if a MongoDB server is running locally on the default port"""
    try:
        client = MongoClient(serverSelectionTimeoutMS=200)
        client.server_info()
        return True
    except ConnectionFailure:
        return False


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not is_db_running(), reason='MongoDB server required for integration tests'),
]


class TestMongoDBCache(BaseStorageTest):
    storage_class = MongoDBCache

    async def test_connection_kwargs(self):
        async with self.init_cache(self.storage_class, host='127.0.0.1') as cache:
            assert await cache.connection.address == ('127.0.0.1', 27017)

    async def test_close(self):
        async with self.init_cache(self.storage_class) as cache:
            cache.connection.close = AsyncMock()
            await cache.close()
            cache.connection.close.assert_awaited_once()

    async def test_close__user_provided_connection(self):
        connection = AsyncMongoClient()
        connection.close = AsyncMock()
        async with self.init_cache(self.storage_class, connection=connection) as cache:
            await cache.close()
            connection.close.assert_not_awaited()

    async def test_values_many(self):
        # If some entries are missing the "data" field for some reason, they
        # should not be returned with the results.
        async with self.init_cache(self.storage_class) as cache:
            await cache.collection.insert_many({'data': f'value_{i}'} for i in range(10))
            await cache.collection.insert_many({'not_data': f'value_{i}'} for i in range(10))
            actual_results = [v async for v in cache.values()]
            assert actual_results == [f'value_{i}' for i in range(10)]


class TestMongoDBPickleCache(TestMongoDBCache):
    storage_class = MongoDBPickleCache
    picklable = True


class TestMongoDBBackend(BaseBackendTest):
    backend_class = MongoDBBackend
