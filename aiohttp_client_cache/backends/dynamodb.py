from .base import BaseCache
from .storage.dynamodbdict import DynamoDbDict


class DynamoDbCache(BaseCache):
    """DynamoDB cache backend"""

    def __init__(self, cache_name: str, *args, **kwargs):
        """See :py:class:`.DynamoDbDict` for backend-specific options"""
        super().__init__(cache_name, *args, **kwargs)
        self.responses = DynamoDbDict(cache_name, 'responses', **kwargs)
        self.keys_map = DynamoDbDict(cache_name, 'urls', self.responses.connection)
