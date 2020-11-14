from aiohttp_client_cache.backends.base import BaseCache

# Import all backends for which dependencies have been installed
try:
    # Heroku doesn't allow the SQLite3 module to be installed
    from .sqlite import DbCache
except ImportError:
    DbCache = None
try:
    from .mongo import MongoCache, MongoDict
except ImportError:
    MongoCache = None
try:
    from .gridfs import GridFSCache
except ImportError:
    GridFSCache = None
try:
    from .redis import RedisCache
except ImportError:
    RedisCache = None
try:
    from .dynamodb import DynamoDbCache
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
PICKLE_PROTOCOL = 4


def create_backend(backend_name, *args, **kwargs):
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

    return backend_class(*args, **kwargs)
