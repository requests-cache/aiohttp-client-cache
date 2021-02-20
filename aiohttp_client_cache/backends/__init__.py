from aiohttp_client_cache.backends.base import (  # noqa: F401
    BaseCache,
    CacheBackend,
    DictCache,
    ResponseOrKey,
)

# Import all backends for which dependencies are installed
try:
    from aiohttp_client_cache.backends.dynamodb import DynamoDBBackend
except ImportError:
    DynamoDBBackend = None  # type: ignore
try:
    from aiohttp_client_cache.backends.gridfs import GridFSBackend
except ImportError:
    GridFSBackend = None  # type: ignore
try:
    from aiohttp_client_cache.backends.mongo import MongoDBBackend
except ImportError:
    MongoDBBackend = None  # type: ignore
try:
    from aiohttp_client_cache.backends.redis import RedisBackend
except ImportError:
    RedisBackend = None  # type: ignore
try:
    from aiohttp_client_cache.backends.sqlite import SQLiteBackend
except ImportError:
    SQLiteBackend = None  # type: ignore
