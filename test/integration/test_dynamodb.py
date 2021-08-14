import asyncio
from typing import Any, Dict

import aioboto3
import pytest

from aiohttp_client_cache.backends.dynamodb import DynamoDBBackend, DynamoDbCache
from test.integration import BaseBackendTest, BaseStorageTest

resource_kwargs = {
    'region_name': 'region',
    'aws_access_key_id': 'access_key_id',
    'aws_secret_access_key': 'secret_access_key',
    'endpoint_url': 'http://localhost:8000',
}


def is_dynamodb_running():
    """Test if a DynamoDB service is running locally"""

    async def check_dynamodb():
        async with aioboto3.resource('dynamodb', **resource_kwargs) as resource:
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


class TestDynamoDbCache(BaseStorageTest):
    storage_class = DynamoDbCache
    picklable = True
    init_kwargs = {
        'create_if_not_exists': True,
        'key_attr_name': 'k',
        'val_attr_name': 'v',
        **resource_kwargs,
    }


class TestDynamoDBBackend(BaseBackendTest):
    backend_class = DynamoDBBackend
    init_kwargs: Dict[str, Any] = {'create_if_not_exists': True, **resource_kwargs}
