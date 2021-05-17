from typing import AsyncIterable, Dict

import aioboto3
from aioboto3.session import ResourceCreatorContext, Session
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
        if not context:
            resource_kwargs = get_valid_kwargs(Session.resource, kwargs)
            context = aioboto3.resource("dynamodb", **resource_kwargs)
        self.responses = DynamoDbCache(
            cache_name, 'resp', key_attr_name, val_attr_name, create_if_not_exists, context
        )
        self.redirects = DynamoDbCache(
            cache_name, 'redir', key_attr_name, val_attr_name, create_if_not_exists, context
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
        key_attr_name: str,
        val_attr_name: str,
        create_if_not_exists: bool,
        context: ResourceCreatorContext,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.table_name = table_name
        self.namespace = namespace
        self.key_attr_name = key_attr_name
        self.val_attr_name = val_attr_name
        self.create_if_not_exists = create_if_not_exists
        self.context = context
        self._table = None

    async def get_table(self):
        if not self._table:
            # Re-use the service resource if it's already been created
            if self.context.cls:
                conn = self.context.cls
            # otherwise create
            else:
                # should we try to call aexit later if we auto enter here?
                conn = await self.context.__aenter__()

            self._table = await conn.Table(self.table_name)
            if self.create_if_not_exists:
                try:
                    await conn.create_table(
                        AttributeDefinitions=[
                            {
                                'AttributeName': self.key_attr_name,
                                'AttributeType': 'S',
                            },
                        ],
                        TableName=self.table_name,
                        KeySchema=[
                            {
                                'AttributeName': self.key_attr_name,
                                'KeyType': 'HASH',
                            },
                        ],
                        BillingMode="PAY_PER_REQUEST",
                    )
                    await self._table.wait_until_exists()
                except ClientError as e:
                    if e.response["Error"]["Code"] != "ResourceInUseException":
                        raise

        return self._table

    def _doc(self, key) -> Dict:
        return {self.key_attr_name: f'{self.namespace}:{key}'}

    async def _scan(self) -> AsyncIterable[Dict]:
        table = await self.get_table()
        client = table.meta.client
        paginator = client.get_paginator('scan')
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
        count = 0
        async for item in self._scan():
            count += 1
        return count

    async def values(self) -> AsyncIterable[ResponseOrKey]:
        async for item in self._scan():
            yield self.deserialize(item[self.val_attr_name].value)
