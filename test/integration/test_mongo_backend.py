import pytest
from bson.objectid import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

from aiohttp_client_cache.backends.mongo import MongoDBBackend, MongoDBCache


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


@pytest.fixture(autouse=True, scope='function')
async def cache_client():
    """Fixture that creates a new db client for each test function"""
    cache_client = MongoDBCache('aiohttp-cache', 'responses')
    await cache_client.clear()
    yield cache_client
    await cache_client.clear()


def test_backend_init():
    backend = MongoDBBackend('aiohttp-cache')
    assert backend.responses.connection == backend.redirects.connection


async def test_clear(cache_client):
    # Put some stuff in the DB
    await cache_client.collection.insert_many({"x": i} for i in range(10))

    # Validate that DB is non-empty
    docs = await cache_client.collection.count_documents({})
    assert docs == 10

    # Clear collection and validate that it's empty
    await cache_client.clear()

    docs = await cache_client.collection.count_documents({})
    assert docs == 0


async def test_contains_true(cache_client):
    _id = (await cache_client.collection.insert_one({"test": "obj"})).inserted_id
    result = await cache_client.contains(_id)
    assert result is True


async def test_contains_false(cache_client):
    result = await cache_client.contains("some_id")
    assert result is False


async def test_deletes_only_doc(cache_client):
    # Insert one doc and validate its existence
    _id = (await cache_client.collection.insert_one({"test": "obj"})).inserted_id
    doc = await cache_client.collection.find_one({"_id": _id})
    assert doc

    # Delete doc and validate its deletion
    await cache_client.delete(_id)
    doc = await cache_client.collection.find_one({"_id": _id})
    assert not doc


async def test_deletes_one_of_many(cache_client):
    # Insert a bunch of docs
    inserted_ids = (
        await cache_client.collection.insert_many({"x": i} for i in range(10))
    ).inserted_ids
    num_docs = await cache_client.collection.count_documents({})
    assert num_docs == 10

    # Delete one of them
    _id = inserted_ids[0]
    await cache_client.delete(_id)
    doc = await cache_client.collection.find_one({"_id": _id})
    assert not doc

    num_docs = await cache_client.collection.count_documents({})
    assert num_docs == 9


async def test_keys_many(cache_client):
    expected_ids = (
        await cache_client.collection.insert_many({"x": i} for i in range(10))
    ).inserted_ids
    actual_ids = {k async for k in cache_client.keys()}
    assert actual_ids == set(expected_ids)


async def test_keys_empty(cache_client):
    actual_ids = {k async for k in cache_client.keys()}
    assert actual_ids == set()


async def test_read_exists(cache_client):
    expected_data = "some_data"
    _id = (await cache_client.collection.insert_one({"data": expected_data})).inserted_id
    actual_data = await cache_client.read(_id)
    assert actual_data == expected_data


async def test_read_does_not_exist(cache_client):
    fake_id = ObjectId("0" * 24)
    actual_data = await cache_client.read(fake_id)
    assert not actual_data


async def test_size_nonzero(cache_client):
    await cache_client.collection.insert_many({"x": i} for i in range(10))
    expected_size = 10
    actual_size = await cache_client.size()
    assert actual_size == expected_size


async def test_size_zero(cache_client):
    expected_size = 0
    actual_size = await cache_client.size()
    assert actual_size == expected_size


async def test_write_does_not_exist(cache_client):
    await cache_client.write("some_key", "some_data")
    doc = await cache_client.collection.find_one({"_id": "some_key"})
    assert doc
    assert doc["data"] == "some_data"


async def test_write_does_exist(cache_client):
    _id = (
        await cache_client.collection.insert_one({"_id": "some_key", "data": "old_data"})
    ).inserted_id
    await cache_client.write(_id, "new_data")

    doc = await cache_client.collection.find_one({"_id": _id})
    assert doc
    assert doc["data"] == "new_data"


async def test_values_none(cache_client):
    actual_results = {v async for v in cache_client.values()}
    assert actual_results == set()


async def test_values_many(cache_client):
    # If some entries are missing the "data" field for some reason, they
    # should not be returned with the results.
    await cache_client.collection.insert_many({"data": i} for i in range(10))
    await cache_client.collection.insert_many({"not_data": i} for i in range(10))
    actual_results = {v async for v in cache_client.values()}
    assert actual_results == set(range(10))
