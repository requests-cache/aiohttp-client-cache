import pickle
from typing import Dict, Iterable

import boto3
from boto3.resources.base import ServiceResource
from botocore.exceptions import ClientError

from aiohttp_client_cache.backends import BaseCache, CacheBackend, ResponseOrKey
from aiohttp_client_cache.forge_utils import extend_signature


class DynamoDBBackend(CacheBackend):
    """DynamoDB cache backend.
    See :py:class:`.DynamoDbCache` for backend-specific options
    See `DynamoDB Service Resource
    <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/dynamodb.html#service-resource>`_
    for more usage details.

    See :py:class:`.CacheBackend` for args.
    """

    @extend_signature(CacheBackend.__init__)
    def __init__(self, cache_name: str = 'aiohttp-cache', **kwargs):
        super().__init__(cache_name=cache_name, **kwargs)
        self.responses = DynamoDbCache(cache_name, 'responses', **kwargs)
        self.redirects = DynamoDbCache(
            cache_name, 'redirects', connection=self.responses.connection
        )


# TODO: Incomplete/untested
# TODO: Fully async implementation. Current implementation with boto3 uses blocking operations.
#   Methods are currently defined as async only for compatibility with BaseCache API.
class DynamoDbCache(BaseCache):
    """An async-compatible interface for caching objects in a DynamoDB key-store

    The actual key name on the dynamodb server will be ``namespace:table_name``.
    In order to deal with how dynamodb stores data/keys, all values must be pickled.

    Args:
        table_name: Table name to use
        namespace: Name of the hash map stored in dynamodb
        connection: An existing resource object to reuse instead of creating a new one
        region_name: AWS region of DynamoDB database
        kwargs: Additional keyword arguments for DynamoDB :py:class:`.ServiceResource`
    """

    def __init__(
        self,
        table_name: str,
        namespace: str = 'dynamodb_dict_data',
        connection: ServiceResource = None,
        region_name: str = 'us-east-1',
        read_capacity_units: int = 1,
        write_capacity_units: int = 1,
        **kwargs,
    ):
        self.namespace = namespace
        self.connection = connection or boto3.resource(
            'dynamodb', region_name=region_name, **kwargs
        )

        # Create the table if it doesn't already exist
        try:
            self.connection.create_table(
                AttributeDefinitions=[
                    {
                        'AttributeName': 'namespace',
                        'AttributeType': 'S',
                    },
                    {
                        'AttributeName': 'key',
                        'AttributeType': 'S',
                    },
                ],
                TableName=table_name,
                KeySchema=[
                    {'AttributeName': 'namespace', 'KeyType': 'HASH'},
                    {'AttributeName': 'key', 'KeyType': 'RANGE'},
                ],
                ProvisionedThroughput={
                    'ReadCapacityUnits': read_capacity_units,
                    'WriteCapacityUnits': write_capacity_units,
                },
            )
        except ClientError:
            pass

        self._table = self.connection.Table(table_name)
        self._table.wait_until_exists()

    def _scan_table(self) -> Dict:
        return self._table.query(
            ExpressionAttributeValues={':Namespace': self.namespace},
            ExpressionAttributeNames={'#N': 'namespace'},
            KeyConditionExpression='#N = :Namespace',
        )

    @staticmethod
    def unpickle(response_item: Dict) -> ResponseOrKey:
        return BaseCache.unpickle((response_item or {}).get('value'))

    async def clear(self):
        response = self._scan_table()
        for v in response['Items']:
            composite_key = {'namespace': v['namespace'], 'key': v['key']}
            self._table.delete_item(Key=composite_key)

    # TODO
    async def contains(self, key: str) -> bool:
        raise NotImplementedError

    async def delete(self, key: str):
        composite_key = {'namespace': self.namespace, 'key': str(key)}
        response = self._table.delete_item(Key=composite_key, ReturnValues='ALL_OLD')
        if 'Attributes' not in response:
            raise KeyError

    # TODO
    async def keys(self) -> Iterable[str]:
        raise NotImplementedError

    async def read(self, key: str) -> ResponseOrKey:
        response = self._table.get_item(Key={'namespace': self.namespace, 'key': str(key)})
        return self.unpickle(response.get('Item'))

    async def size(self) -> int:
        expression_attribute_values = {':Namespace': self.namespace}
        expression_attribute_names = {'#N': 'namespace'}
        key_condition_expression = '#N = :Namespace'
        return self._table.query(
            Select='COUNT',
            ExpressionAttributeValues=expression_attribute_values,
            ExpressionAttributeNames=expression_attribute_names,
            KeyConditionExpression=key_condition_expression,
        )['Count']

    async def values(self) -> Iterable[ResponseOrKey]:
        response = self._scan_table()
        return [self.unpickle(item) for item in response.get('Items', [])]

    async def write(self, key: str, item: ResponseOrKey):
        item_meta = {
            'namespace': self.namespace,
            'key': str(key),
            'value': pickle.dumps(item, protocol=-1),
        }
        self._table.put_item(Item=item_meta)
