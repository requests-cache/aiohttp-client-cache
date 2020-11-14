from collections.abc import MutableMapping
import pickle

from pymongo import MongoClient

from aiohttp_client_cache.backends import PICKLE_PROTOCOL, BaseCache


class MongoCache(BaseCache):
    """MongoDB cache backend"""

    def __init__(self, cache_name: str, *args, connection: MongoClient = None, **kwargs):
        super().__init__(cache_name, *args, **kwargs)
        self.responses = MongoPickleDict(cache_name, 'responses', connection)
        self.keys_map = MongoDict(cache_name, 'urls', self.responses.connection)


class MongoDict(MutableMapping):
    """A dictionary-like interface for ``mongo`` database"""

    def __init__(self, db_name, collection_name: str, connection: MongoClient = None):
        """
        Args:
            db_name: database name (be careful with production databases)
            collection_name: collection name
            connection: MongoDB connection instance to use instead of creating a new one
        """
        self.connection = connection or MongoClient()
        self.db = self.connection[db_name]
        self.collection = self.db[collection_name]

    def __getitem__(self, key):
        result = self.collection.find_one({'_id': key})
        if result is None:
            raise KeyError
        return result['data']

    def __setitem__(self, key, item):
        self.collection.save({'_id': key, 'data': item})

    def __delitem__(self, key):
        spec = {'_id': key}
        if hasattr(self.collection, "find_one_and_delete"):
            res = self.collection.find_one_and_delete(spec, {'_id': True})
        else:
            res = self.collection.find_and_modify(spec, remove=True, fields={'_id': True})

        if res is None:
            raise KeyError

    def __len__(self):
        return self.collection.count()

    def __iter__(self):
        for d in self.collection.find({}, {'_id': True}):
            yield d['_id']

    def clear(self):
        self.collection.drop()

    def __str__(self):
        return str(dict(self.items()))


class MongoPickleDict(MongoDict):
    """Same as :class:`MongoDict`, but pickles values before saving"""

    def __setitem__(self, key, item):
        super().__setitem__(key, pickle.dumps(item, protocol=PICKLE_PROTOCOL))

    def __getitem__(self, key):
        return pickle.loads(bytes(super().__getitem__(key)))
