from aiohttp_client_cache.backends.base import DictCache
from test.integration import BaseStorageTest


class TestDictCache(BaseStorageTest):
    storage_class = DictCache
