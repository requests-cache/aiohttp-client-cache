from importlib import import_module
from logging import getLogger
from typing import Optional, Type

from aiohttp_client_cache.backends.base import (  # noqa
    BaseCache,
    CacheController,
    DictCache,
    ResponseOrKey,
)

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
BACKEND_QUALNAMES = {
    'dynamodb': 'aiohttp_client_cache.backends.dynamodb.DynamoDbController',
    'gridfs': 'aiohttp_client_cache.backends.gridfs.GridFSController',
    'memory': 'aiohttp_client_cache.backends.base.CacheController',
    'mongodb': 'aiohttp_client_cache.backends.mongo.MongoDBController',
    'redis': 'aiohttp_client_cache.backends.redis.RedisController',
    'sqlite': 'aiohttp_client_cache.backends.sqlite.SQLiteController',
}
BACKEND_CLASSES = {name: import_member(qualname) for name, qualname in BACKEND_QUALNAMES.items()}


def init_backend(
    backend: Optional[str] = None, cache_name: str = 'http-cache', *args, **kwargs
) -> CacheController:
    """Initialize a backend by name; defaults to ``sqlite`` if installed, otherwise ``memory``"""
    logger.info(f'Initializing backend: {backend}')
    if isinstance(backend, CacheController):
        return backend
    if not backend:
        backend = 'sqlite' if 'sqlite' in BACKEND_CLASSES else 'memory'
    backend = backend.lower()

    if backend not in BACKEND_QUALNAMES:
        raise ValueError(f'Invalid backend: {backend}')
    backend_class = BACKEND_CLASSES.get(backend)
    if not backend_class:
        raise ImportError(f'Dependencies not installed for backend {backend}')

    logger.info(f'Found backend type: {backend_class}')
    return backend_class(cache_name, *args, **kwargs)
