import os
import sys

sys.path.insert(0, os.path.abspath('..'))

import unittest

from tests.test_custom_dict import BaseCustomDictTestCase

from aiohttp_client_cache.backends.storage.dynamodbdict import DynamoDbDict


class WrapDynamoDbDict(DynamoDbDict):
    def __init__(self, namespace, collection_name='dynamodb_dict_data', **options):
        options['endpoint_url'] = (
            os.environ['DYNAMODB_ENDPOINT_URL'] if 'DYNAMODB_ENDPOINT_URL' in os.environ else None
        )
        super(WrapDynamoDbDict, self).__init__(namespace, collection_name, **options)


class DynamoDbDictTestCase(BaseCustomDictTestCase, unittest.TestCase):
    dict_class = WrapDynamoDbDict
    pickled_dict_class = WrapDynamoDbDict
