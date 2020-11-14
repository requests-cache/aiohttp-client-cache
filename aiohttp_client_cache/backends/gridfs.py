from .base import BaseCache
from .storage.mongodict import MongoDict
from .storage.gridfspickledict import GridFSPickleDict


class GridFSCache(BaseCache):
    """GridFS cache backend.
    Use MongoDB GridFS to support documents greater than 16MB.

    Usage:
        aiohttp_client_cache.install_cache(backend='gridfs')

    Or:
        from pymongo import MongoClient
        aiohttp_client_cache.install_cache(backend='gridfs', connection=MongoClient('another-host.local'))
    """

    def __init__(self, db_name, **options):
        """
        :param db_name: database name
        :param connection: (optional) ``pymongo.Connection``
        """
        super().__init__(**options)
        self.responses = GridFSPickleDict(db_name, options.get('connection'))
        self.keys_map = MongoDict(db_name, 'http_redirects', self.responses.connection)
