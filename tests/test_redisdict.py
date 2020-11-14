import os, sys

sys.path.insert(0, os.path.abspath('..'))
import unittest

from aiohttp_client_cache.backends.storage.redisdict import RedisDict
from tests.test_custom_dict import BaseCustomDictTestCase


class RedisDictTestCase(BaseCustomDictTestCase, unittest.TestCase):
    dict_class = RedisDict
    pickled_dict_class = RedisDict
