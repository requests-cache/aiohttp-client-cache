import pytest

from bson.objectid import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from aiohttp_client_cache.backends.mongo import MongoDBCache

from . import backends_to_test


@pytest.mark.skipif(
    "mongo" not in backends_to_test(),
    reason="MongoDB backend tests must be explicitly enabled; a local MongoDB server is required.",
)
class TestMongoDBCache:
    pytestmark = pytest.mark.asyncio

    db_name = "aiohttp_client_cache_pytest"
    collection_name = "fake-collection"

    def setup(self):
        self.connection = AsyncIOMotorClient()
        self.db = self.connection[self.db_name]
        self.collection = self.db[self.collection_name]
        self.cache_client = MongoDBCache(self.db_name, self.collection_name, self.connection)

    @pytest.fixture(autouse=True)
    async def drop_db(self, event_loop):
        # We need to recreate the Motor client for every test method,
        # else it will be using a different event loop than pytest.
        self.setup()
        await self.connection.drop_database(self.db_name)
        yield
        await self.connection.drop_database(self.db_name)

    async def test_clear(self):
        # Put some stuff in the DB
        await self.collection.insert_many({"x": i} for i in range(10))

        # Validate that DB is non-empty
        docs = await self.collection.count_documents({})
        assert docs == 10

        # Clear collection and validate that it's empty
        await self.cache_client.clear()

        docs = await self.collection.count_documents({})
        assert docs == 0

    async def test_contains_true(self):
        _id = (await self.collection.insert_one({"test": "obj"})).inserted_id
        result = await self.cache_client.contains(_id)
        assert result is True

    async def test_contains_false(self):
        result = await self.cache_client.contains("some_id")
        assert result is False

    async def test_deletes_only_doc(self):
        # Insert one doc and validate its existence
        _id = (await self.collection.insert_one({"test": "obj"})).inserted_id
        doc = await self.collection.find_one({"_id": _id})
        assert doc

        # Delete doc and validate its deletion
        await self.cache_client.delete(_id)
        doc = await self.collection.find_one({"_id": _id})
        assert not doc

    async def test_deletes_one_of_many(self):
        # Insert a bunch of docs
        inserted_ids = (await self.collection.insert_many({"x": i} for i in range(10))).inserted_ids
        num_docs = await self.collection.count_documents({})
        assert num_docs == 10

        # Delete one of them
        _id = inserted_ids[0]
        await self.cache_client.delete(_id)
        doc = await self.collection.find_one({"_id": _id})
        assert not doc

        num_docs = await self.collection.count_documents({})
        assert num_docs == 9

    async def test_keys_many(self):
        expected_ids = (await self.collection.insert_many({"x": i} for i in range(10))).inserted_ids
        actual_ids = await self.cache_client.keys()
        assert set(actual_ids) == set(expected_ids)

    async def test_keys_empty(self):
        actual_ids = await self.cache_client.keys()
        assert set(actual_ids) == set()

    async def test_read_exists(self):
        expected_data = "some_data"
        _id = (await self.collection.insert_one({"data": expected_data})).inserted_id
        actual_data = await self.cache_client.read(_id)
        assert actual_data == expected_data

    async def test_read_does_not_exist(self):
        fake_id = ObjectId("0" * 24)
        actual_data = await self.cache_client.read(fake_id)
        assert not actual_data

    async def test_size_nonzero(self):
        await self.collection.insert_many({"x": i} for i in range(10))
        expected_size = 10
        actual_size = await self.cache_client.size()
        assert actual_size == expected_size

    async def test_size_zero(self):
        expected_size = 0
        actual_size = await self.cache_client.size()
        assert actual_size == expected_size

    async def test_write_does_not_exist(self):
        await self.cache_client.write("some_key", "some_data")
        doc = await self.collection.find_one({"_id": "some_key"})
        assert doc
        assert doc["data"] == "some_data"

    async def test_write_does_exist(self):
        _id = (
            await self.collection.insert_one({"_id": "some_key", "data": "old_data"})
        ).inserted_id
        await self.cache_client.write(_id, "new_data")

        doc = await self.collection.find_one({"_id": _id})
        assert doc
        assert doc["data"] == "new_data"

    async def test_values_none(self):
        actual_results = await self.cache_client.values()
        assert set(actual_results) == set()

    async def test_values_many(self):
        # If some entries are missing the "data" field for some reason, they
        # should not be returned with the results.
        await self.collection.insert_many({"data": i} for i in range(10))
        await self.collection.insert_many({"not_data": i} for i in range(10))
        actual_results = await self.cache_client.values()
        expected_results = set(range(10))
        assert set(actual_results) == expected_results
