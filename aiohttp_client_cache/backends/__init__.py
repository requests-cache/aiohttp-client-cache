from logging import getLogger
from importlib import import_module
from typing import Optional

from aiohttp_client_cache.backends.base import BaseCache

PICKLE_PROTOCOL = 4
logger = getLogger(__name__)

# Import all backends for which dependencies have been installed
try:
    # Heroku doesn't allow the SQLite3 module to be installed
    from aiohttp_client_cache.backends.sqlite import DbCache
except ImportError:
    DbCache = None
try:
    from aiohttp_client_cache.backends.mongo import MongoCache, MongoDict
except ImportError:
    MongoCache, MongoDict = None, None
try:
    from aiohttp_client_cache.backends.gridfs import GridFSCache
except ImportError:
    GridFSCache = None
try:
    from aiohttp_client_cache.backends.redis import RedisCache
except ImportError:
    RedisCache = None
try:
    from aiohttp_client_cache.backends.dynamodb import DynamoDbCache
except ImportError:
    DynamoDbCache = None

BACKEND_CLASSES = {
    'dynamodb': DynamoDbCache,
    'gridfs': GridFSCache,
    'memory': BaseCache,
    'mongo': MongoCache,
    'mongodb': MongoCache,
    'redis': RedisCache,
    'sqlite': DbCache,
}


def create_backend(backend_name: Optional[str], *args, **kwargs):
    """Initialize a backend by name"""
    logger.info(f'Initializing backend: {backend_name}')
    if isinstance(backend_name, BaseCache):
        return backend_name
    if not backend_name:
        backend_name = 'sqlite' if BACKEND_CLASSES['sqlite'] else 'memory'
    backend_name = backend_name.lower()

    if backend_name not in BACKEND_CLASSES:
        raise ValueError(f'Invalid backend: {backend_name}')
    backend_class = BACKEND_CLASSES.get(backend_name)
    if not backend_class:
        raise ImportError(f'Dependencies not installed for backend {backend_name}')

    logger.info(f'Found backend type: {backend_class}')
    return backend_class(*args, **kwargs)
