from contextlib import asynccontextmanager
from typing import AsyncIterable, Dict

import aioboto3
from aioboto3.session import ResourceCreatorContext
from aioboto3.session import Session as AWSSession
from botocore.exceptions import ClientError

from aiohttp_client_cache.backends import BaseCache, CacheBackend, ResponseOrKey, get_valid_kwargs
from aiohttp_client_cache.docs import dynamodb_template, extend_init_signature


@extend_init_signature(CacheBackend, dynamodb_template)
class DynamoDBBackend(CacheBackend):
    """Async cache backend for `DynamoDB <https://aws.amazon.com/dynamodb>`_
    (requires `aioboto3 <https://aioboto3.readthedocs.io>`_)

    See `DynamoDB Service Resource
    <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/dynamodb.html#service-resource>`_
    for more usage details.
    """

    def __init__(
        self,
        cache_name: str = 'aiohttp-cache',
        key_attr_name: str = 'k',
        val_attr_name: str = 'v',
        create_if_not_exists: bool = False,
        context: ResourceCreatorContext = None,
        **kwargs,
    ):
        """
        Args:
            cache_name: Table name to use
            key_attr_name: The name of the field to use for keys in the DynamoDB document
            val_attr_name: The name of the field to use for values in the DynamoDB document
            create_if_not_exists: Whether or not to attempt to create the DynamoDB table
            context: An existing `ResourceCreatorContext <https://aioboto3.readthedocs.io/en/latest/usage.html>`_
                to reuse instead of creating a new one
        """
        super().__init__(cache_name=cache_name, **kwargs)
        self.responses = DynamoDbCache(
            cache_name,
            'resp',
            key_attr_name,
            val_attr_name,
            create_if_not_exists,
            context=context,
            **kwargs,
        )
        self.redirects = DynamoDbCache(
            cache_name,
            'redir',
            key_attr_name,
            val_attr_name,
            create_if_not_exists,
            context=self.responses.context,
            **kwargs,
        )


class DynamoDbCache(BaseCache):
    """An async interface for caching objects in a DynamoDB key-store

    The actual key name on the dynamodb server will be ``namespace:key``.
    In order to deal with how dynamodb stores data/keys, all values must be serialized.
    """

    def __init__(
        self,
        table_name: str,
        namespace: str,
        key_attr_name: str = 'k',
        val_attr_name: str = 'v',
        create_if_not_exists: bool = False,
        context: ResourceCreatorContext = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.table_name = table_name
        self.namespace = namespace
        self.key_attr_name = key_attr_name
        self.val_attr_name = val_attr_name
        self.create_if_not_exists = create_if_not_exists

        resource_kwargs = get_valid_kwargs(AWSSession.resource, kwargs)
        self.context = context or aioboto3.resource('dynamodb', **resource_kwargs)
        self._table = None

    @asynccontextmanager
    async def get_connection(self):
        # Re-use the service resource if it's already been created
        if self.context.cls:
            yield self.context.cls
        else:
            yield await self.context.__aenter__()

    async def get_table(self):
        if not self._table:
            async with self.get_connection() as conn:
                if self.create_if_not_exists:
                    self._table = await self._create_table(conn)
                else:
                    self._table = await conn.Table(self.table_name)
        return self._table

    async def _create_table(self, conn):
        table = await conn.Table(self.table_name)

        try:
            await conn.create_table(
                AttributeDefinitions=[{'AttributeName': self.key_attr_name, 'AttributeType': 'S'}],
                TableName=self.table_name,
                KeySchema=[{'AttributeName': self.key_attr_name, 'KeyType': 'HASH'}],
                BillingMode="PAY_PER_REQUEST",
            )
            await table.wait_until_exists()
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceInUseException":
                raise

        return table

    def _doc(self, key) -> Dict:
        return {self.key_attr_name: f'{self.namespace}:{key}'}

    async def _scan(self) -> AsyncIterable[Dict]:
        table = await self.get_table()
        paginator = table.meta.client.get_paginator('scan')
        iterator = paginator.paginate(
            TableName=table.name,
            Select='ALL_ATTRIBUTES',
            FilterExpression=f'begins_with({self.key_attr_name}, :namespace)',
            ExpressionAttributeValues={':namespace': f'{self.namespace}:'},
        )
        async for result in iterator:
            for item in result['Items']:
                yield item

    async def delete(self, key: str) -> None:
        doc = self._doc(key)
        table = await self.get_table()
        await table.delete_item(Key=doc)

    async def read(self, key: str) -> ResponseOrKey:
        table = await self.get_table()
        response = await table.get_item(Key=self._doc(key), ProjectionExpression=self.val_attr_name)
        item = response.get("Item")
        if item:
            return self.deserialize(item[self.val_attr_name].value)
        return None

    async def write(self, key: str, item: ResponseOrKey) -> None:
        table = await self.get_table()
        doc = self._doc(key)
        doc[self.val_attr_name] = self.serialize(item)
        await table.put_item(Item=doc)

    async def clear(self) -> None:
        async for key in self.keys():
            await self.delete(key)

    async def contains(self, key: str) -> bool:
        resp = await self.read(key)
        return resp is not None

    async def keys(self) -> AsyncIterable[str]:
        len_prefix = len(self.namespace) + 1
        async for item in self._scan():
            yield item[self.key_attr_name][len_prefix:]

    async def size(self) -> int:
        return len([i async for i in self._scan()])

    async def values(self) -> AsyncIterable[ResponseOrKey]:
        async for item in self._scan():
            yield self.deserialize(item[self.val_attr_name].value)
