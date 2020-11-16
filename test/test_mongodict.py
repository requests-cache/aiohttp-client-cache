import os
import sys

sys.path.insert(0, os.path.abspath('..'))

import unittest

from tests.test_custom_dict import BaseCustomDictTestCase

from aiohttp_client_cache.backends.storage.mongodict import MongoDict, MongoPickleDict


class MongoDictTestCase(BaseCustomDictTestCase, unittest.TestCase):
    dict_class = MongoDict
    pickled_dict_class = MongoPickleDict
