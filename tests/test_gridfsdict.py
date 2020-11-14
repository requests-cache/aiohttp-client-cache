#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Path hack
import os, sys

sys.path.insert(0, os.path.abspath('..'))

try:
    import unittest2 as unittest
except ImportError:
    import unittest

from tests.test_custom_dict import BaseCustomDictTestCase

try:
    from aiohttp_client_cache.backends.storage.mongodict import MongoDict
    from aiohttp_client_cache.backends.storage.gridfspickledict import GridFSPickleDict

except ImportError:
    print("pymongo not installed")
else:

    class MongoDictTestCase(BaseCustomDictTestCase, unittest.TestCase):
        dict_class = MongoDict
        pickled_dict_class = GridFSPickleDict

    if __name__ == '__main__':
        unittest.main()
