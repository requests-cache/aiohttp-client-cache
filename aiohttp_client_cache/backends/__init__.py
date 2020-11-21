from importlib import import_module
from logging import getLogger
from typing import Optional, Type

from aiohttp_client_cache.backends.base import BaseCache, BaseStorage, DictStorage  # noqa

PICKLE_PROTOCOL = 4
BACKEND_QUALNAMES = {
    'dynamodb': 'aiohttp_client_cache.backends.dynamodb.DynamoDbCache',
    'gridfs': 'aiohttp_client_cache.backends.gridfs.GridFSCache',
    'memory': 'aiohttp_client_cache.backends.base.BaseCache',
    'mongodb': 'aiohttp_client_cache.backends.mongo.MongoCache',
    'redis': 'aiohttp_client_cache.backends.redis.RedisCache',
    'sqlite': 'aiohttp_client_cache.backends.sqlite.DbCache',
}
logger = getLogger(__name__)


def import_member(qualname: str) -> Optional[Type]:
    """Attempt to import a class or other module member by qualified name"""
    try:
        module, member = qualname.rsplit('.', 1)
        return getattr(import_module(module), member)
    except (AttributeError, ImportError) as e:
        logger.debug(f'Could not load {qualname}: {str(e)}')
        return None


# Import all backends for which dependencies have been installed
BACKEND_CLASSES = {name: import_member(qualname) for name, qualname in BACKEND_QUALNAMES.items()}


def create_backend(backend_name: Optional[str], *args, **kwargs) -> BaseCache:
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
