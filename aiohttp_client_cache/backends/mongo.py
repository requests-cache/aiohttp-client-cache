import pymongo

from .base import BaseCache
from .storage.mongodict import MongoDict, MongoPickleDict


class MongoCache(BaseCache):
    """MongoDB cache backend"""

    def __init__(self, cache_name: str, *args, connection: pymongo.MongoClient = None, **kwargs):
        super().__init__(cache_name, *args, **kwargs)
        self.responses = MongoPickleDict(cache_name, 'responses', connection)
        self.keys_map = MongoDict(cache_name, 'urls', self.responses.connection)
