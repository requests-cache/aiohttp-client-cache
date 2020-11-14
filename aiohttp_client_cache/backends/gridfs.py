from collections.abc import MutableMapping
import pickle

from gridfs import GridFS
from pymongo import MongoClient

from aiohttp_client_cache.backends import PICKLE_PROTOCOL, BaseCache, MongoDict


class GridFSCache(BaseCache):
    """GridFS cache backend.
    Use MongoDB GridFS to support documents greater than 16MB.

    Example:

        >>> aiohttp_client_cache.install_cache(backend='gridfs')
        >>> # Or:
        >>> from pymongo import MongoClient
        >>> aiohttp_client_cache.install_cache(backend='gridfs', connection=MongoClient('another-host.local'))

    """

    def __init__(self, cache_name: str, *args, connection: MongoClient = None, **kwargs):
        super().__init__(cache_name, *args, **kwargs)
        self.responses = GridFSPickleDict(cache_name, connection)
        self.keys_map = MongoDict(cache_name, 'http_redirects', self.responses.connection)


class GridFSPickleDict(MutableMapping):
    """A dictionary-like interface for MongoDB GridFS"""

    def __init__(self, db_name, connection: MongoClient = None):
        """
        Args:
            db_name: database name (be careful with production databases)
            connection: MongoDB connection instance to use instead of creating a new one
        """
        self.connection = connection or MongoClient()
        self.db = self.connection[db_name]
        self.fs = GridFS(self.db)

    def __getitem__(self, key):
        result = self.fs.find_one({'_id': key})
        if result is None:
            raise KeyError
        return pickle.loads(bytes(result.read()))

    def __setitem__(self, key, item):
        self.__delitem__(key)
        self.fs.put(pickle.dumps(item, protocol=PICKLE_PROTOCOL), **{'_id': key})

    def __delitem__(self, key):
        res = self.fs.find_one({'_id': key})
        if res is not None:
            self.fs.delete(res._id)

    def __len__(self):
        return self.db['fs.files'].count()

    def __iter__(self):
        for d in self.fs.find():
            yield d._id

    def clear(self):
        self.db['fs.files'].drop()
        self.db['fs.chunks'].drop()

    def __str__(self):
        return str(dict(self.items()))
