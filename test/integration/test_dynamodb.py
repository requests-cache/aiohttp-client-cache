from typing import Any, Dict

import pytest

from aiohttp_client_cache.backends.dynamodb import DynamoDBBackend, DynamoDbCache
from test.integration import BaseBackendTest, BaseStorageTest

AWS_OPTIONS = {
    'endpoint_url': 'http://localhost:8000',
    'region_name': 'us-east-1',
    'aws_access_key_id': 'placeholder',
    'aws_secret_access_key': 'placeholder',
}


def is_dynamodb_running():
    """Test if a DynamoDB service is running locally"""
    import boto3

    try:
        client = boto3.client('dynamodb', **AWS_OPTIONS)
        client.describe_limits()
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
        **AWS_OPTIONS,
    }


class TestDynamoDBBackend(BaseBackendTest):
    backend_class = DynamoDBBackend
    init_kwargs: Dict[str, Any] = {'create_if_not_exists': True, **AWS_OPTIONS}
