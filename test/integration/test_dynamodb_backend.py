import asyncio
from datetime import datetime

import aioboto3
import pytest

from aiohttp_client_cache.backends.dynamodb import DynamoDBBackend


def local_context():
    return aioboto3.resource(
        "dynamodb",
        region_name='region',
        aws_access_key_id='access_key_id',
        aws_secret_access_key='secret_access_key',
        endpoint_url="http://localhost:8000",
    )


def is_dynamodb_running():
    """Test if a DynamoDB service is running locally"""

    async def check_dynamodb():
        async with local_context() as resource:
            client = resource.meta.client
            await client.describe_limits()

    try:
        asyncio.run(check_dynamodb())
        return True
    except OSError:
        return False


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        not is_dynamodb_running(), reason='local DynamoDB service required for integration tests'
    ),
]

test_data = {'key_1': 'item_1', 'key_2': datetime.now(), 'key_3': 3.141592654}


@pytest.fixture(autouse=True, scope='function')
async def cache_client():
    """Fixture that creates a new cache client for each test function"""
    backend = DynamoDBBackend(create_if_not_exists=True, context=local_context())
    cache_client = backend.responses
    table = await cache_client.get_table()
    yield cache_client
    await table.delete()


async def test_write_read(cache_client):
    for k, v in test_data.items():
        await cache_client.write(k, v)
        assert await cache_client.read(k) == v


async def test_delete(cache_client):
    for k, v in test_data.items():
        await cache_client.write(k, v)

    for k in test_data.keys():
        await cache_client.delete(k)
        assert await cache_client.read(k) is None


async def test_keys_values_size(cache_client):
    for k, v in test_data.items():
        await cache_client.write(k, v)

    assert await cache_client.size() == len(test_data)
    assert {key async for key in cache_client.keys()} == set(test_data.keys())
    assert {val async for val in cache_client.values()} == set(test_data.values())


async def test_clear(cache_client):
    for k, v in test_data.items():
        await cache_client.write(k, v)

    await cache_client.clear()
    assert await cache_client.size() == 0
    assert [key async for key in cache_client.keys()] == []
    assert [val async for val in cache_client.values()] == []
