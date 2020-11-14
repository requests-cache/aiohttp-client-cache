import pymongo

from .base import BaseCache
from .storage.mongodict import MongoDict
from .storage.gridfspickledict import GridFSPickleDict


class GridFSCache(BaseCache):
    """GridFS cache backend.
    Use MongoDB GridFS to support documents greater than 16MB.

    Example:

        >>> aiohttp_client_cache.install_cache(backend='gridfs')
        >>> # Or:
        >>> from pymongo import MongoClient
        >>> aiohttp_client_cache.install_cache(backend='gridfs', connection=MongoClient('another-host.local'))

    """

    def __init__(self, cache_name: str, *args, connection: pymongo.MongoClient = None, **kwargs):
        super().__init__(cache_name, *args, **kwargs)
        self.responses = GridFSPickleDict(cache_name, connection)
        self.keys_map = MongoDict(cache_name, 'http_redirects', self.responses.connection)
