import os, sys

sys.path.insert(0, os.path.abspath('..'))

import unittest

from aiohttp_client_cache.backends.storage.mongodict import MongoDict
from aiohttp_client_cache.backends.storage.gridfspickledict import GridFSPickleDict
from tests.test_custom_dict import BaseCustomDictTestCase


class MongoDictTestCase(BaseCustomDictTestCase, unittest.TestCase):
    dict_class = MongoDict
    pickled_dict_class = GridFSPickleDict