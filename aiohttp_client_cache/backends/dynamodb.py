from collections.abc import MutableMapping
import pickle

import boto3
from boto3.resources.base import ServiceResource
from botocore.exceptions import ClientError

from aiohttp_client_cache.backends import PICKLE_PROTOCOL, BaseCache


class DynamoDbCache(BaseCache):
    """DynamoDB cache backend"""

    def __init__(self, cache_name: str, *args, **kwargs):
        """See :py:class:`.DynamoDbDict` for backend-specific options"""
        super().__init__(cache_name, *args, **kwargs)
        self.responses = DynamoDbDict(cache_name, 'responses', **kwargs)
        self.keys_map = DynamoDbDict(cache_name, 'urls', self.responses.connection)


class DynamoDbDict(MutableMapping):
    """A dictionary-like interface for a DynamoDB key-store"""

    def __init__(
        self,
        table_name: str,
        namespace: str = 'dynamodb_dict_data',
        connection: ServiceResource = None,
        endpoint_url: str = None,
        region_name: str = 'us-east-1',
        read_capacity_units: int = 1,
        write_capacity_units: int = 1,
        **kwargs,
    ):

        """
        The actual key name on the dynamodb server will be ``namespace``:``namespace_name``.
        In order to deal with how dynamodb stores data/keys, everything must be pickled.

        Args:
            table_name: Table name to use
            namespace_name: Name of the hash map stored in dynamodb
            connection: boto3 resource instance to use instead of creating a new one
            endpoint_url: url of dynamodb server
        """
        self._self_key = namespace
        if connection is not None:
            self.connection = connection
        else:
            self.connection = boto3.resource(
                'dynamodb', endpoint_url=endpoint_url, region_name=region_name
            )
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

    def __getitem__(self, key):
        composite_key = {'namespace': self._self_key, 'key': str(key)}
        result = self._table.get_item(Key=composite_key)
        if 'Item' not in result:
            raise KeyError
        return pickle.loads(result['Item']['value'].value)

    def __setitem__(self, key, item):
        item = {
            'namespace': self._self_key,
            'key': str(key),
            'value': pickle.dumps(item, protocol=PICKLE_PROTOCOL),
        }
        self._table.put_item(Item=item)

    def __delitem__(self, key):
        composite_key = {'namespace': self._self_key, 'key': str(key)}
        response = self._table.delete_item(Key=composite_key, ReturnValues='ALL_OLD')
        if 'Attributes' not in response:
            raise KeyError

    def __len__(self):
        return self.__count_table()

    def __iter__(self):
        response = self.__scan_table()
        for v in response['Items']:
            yield pickle.loads(v['value'].value)

    def clear(self):
        response = self.__scan_table()
        for v in response['Items']:
            composite_key = {'namespace': v['namespace'], 'key': v['key']}
            self._table.delete_item(Key=composite_key)

    def __str__(self):
        return str(dict(self.items()))

    def __scan_table(self):
        expression_attribute_values = {':Namespace': self._self_key}
        expression_attribute_names = {'#N': 'namespace'}
        key_condition_expression = '#N = :Namespace'
        return self._table.query(
            ExpressionAttributeValues=expression_attribute_values,
            ExpressionAttributeNames=expression_attribute_names,
            KeyConditionExpression=key_condition_expression,
        )

    def __count_table(self):
        expression_attribute_values = {':Namespace': self._self_key}
        expression_attribute_names = {'#N': 'namespace'}
        key_condition_expression = '#N = :Namespace'
        return self._table.query(
            Select='COUNT',
            ExpressionAttributeValues=expression_attribute_values,
            ExpressionAttributeNames=expression_attribute_names,
            KeyConditionExpression=key_condition_expression,
        )['Count']
