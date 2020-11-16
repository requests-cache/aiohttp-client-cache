import os
import sys

sys.path.insert(0, os.path.abspath('..'))
import unittest

from tests.test_custom_dict import BaseCustomDictTestCase

from aiohttp_client_cache.backends.storage.redisdict import RedisDict


class RedisDictTestCase(BaseCustomDictTestCase, unittest.TestCase):
    dict_class = RedisDict
    pickled_dict_class = RedisDict
