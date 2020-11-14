import redis

from .base import BaseCache
from .storage.redisdict import RedisDict


class RedisCache(BaseCache):
    """Redis cache backend"""

    def __init__(self, cache_name: str, *args, connection: redis.StrictRedis = None, **kwargs):
        super().__init__(cache_name, *args, **kwargs)
        self.responses = RedisDict(cache_name, 'responses', connection)
        self.keys_map = RedisDict(cache_name, 'urls', self.responses.connection)
