import os, sys

sys.path.insert(0, os.path.abspath('..'))

import unittest

import requests
from requests.sessions import Session as OriginalSession

import aiohttp_client_cache
from aiohttp_client_cache import CachedSession
from aiohttp_client_cache.backends import BaseCache


CACHE_NAME = 'requests_cache_test'
CACHE_BACKEND = 'sqlite'
FAST_SAVE = False


class MonkeyPatchTestCase(unittest.TestCase):
    def setUp(self):
        aiohttp_client_cache.install_cache(name=CACHE_NAME, backend=CACHE_BACKEND)
        requests.Session().cache.clear()
        aiohttp_client_cache.uninstall_cache()

    def test_install_uninstall(self):
        for _ in range(2):
            aiohttp_client_cache.install_cache(name=CACHE_NAME, backend=CACHE_BACKEND)
            self.assertTrue(isinstance(requests.Session(), CachedSession))
            self.assertTrue(isinstance(requests.sessions.Session(), CachedSession))
            self.assertTrue(isinstance(requests.session(), CachedSession))
            aiohttp_client_cache.uninstall_cache()
            self.assertFalse(isinstance(requests.Session(), CachedSession))
            self.assertFalse(isinstance(requests.sessions.Session(), CachedSession))
            self.assertFalse(isinstance(requests.session(), CachedSession))

    def test_requests_from_cache(self):
        aiohttp_client_cache.install_cache(name=CACHE_NAME, backend=CACHE_BACKEND)
        r = requests.get('http://httpbin.org/get')
        self.assertFalse(r.from_cache)
        r = requests.get('http://httpbin.org/get')
        self.assertTrue(r.from_cache)

    def test_session_is_a_class_with_original_attributes(self):
        aiohttp_client_cache.install_cache(name=CACHE_NAME, backend=CACHE_BACKEND)
        self.assertTrue(isinstance(requests.Session, type))
        for attribute in dir(OriginalSession):
            self.assertTrue(hasattr(requests.Session, attribute))
        self.assertTrue(isinstance(requests.Session(), CachedSession))

    def test_inheritance_after_monkey_patch(self):
        aiohttp_client_cache.install_cache(name=CACHE_NAME, backend=CACHE_BACKEND)

        class FooSession(requests.Session):
            __attrs__ = requests.Session.__attrs__ + ["new_one"]

            def __init__(self, param):
                self.param = param
                super(FooSession, self).__init__()

        s = FooSession(1)
        self.assertEquals(s.param, 1)
        self.assertIn("new_one", s.__attrs__)
        self.assertTrue(isinstance(s, CachedSession))

    def test_passing_backend_instance_support(self):
        class MyCache(BaseCache):
            pass

        backend = MyCache()
        aiohttp_client_cache.install_cache(name=CACHE_NAME, backend=backend)
        self.assertIs(requests.Session().cache, backend)

        session = CachedSession(backend=backend)
        self.assertIs(session.cache, backend)


if __name__ == '__main__':
    unittest.main()
