from inspect import signature
from logging import getLogger
from typing import Callable, Dict

from aiohttp_client_cache.backends.base import (  # noqa: F401
    BaseCache,
    CacheBackend,
    DictCache,
    ResponseOrKey,
)

logger = getLogger(__name__)


def get_placeholder_backend(original_exception):
    """This creates a placeholder type for a backend class that does not have dependencies
    installed. This allows delaying the ImportError until init is called, rather then when imported.
    """

    class PlaceholderBackend:
        def __init__(*args, **kwargs):
            logger.error('Dependencies are not installed for this backend')
            raise original_exception

    return PlaceholderBackend


def get_valid_kwargs(func: Callable, kwargs: Dict) -> Dict:
    """Get the subset of non-None ``kwargs`` that are valid params for ``func``"""
    params = list(signature(func).parameters)
    return {k: v for k, v in kwargs.items() if k in params and v is not None}


# Import all backends for which dependencies are installed
try:
    from aiohttp_client_cache.backends.dynamodb import DynamoDBBackend
except ImportError as e:
    DynamoDBBackend = get_placeholder_backend(e)  # type: ignore
try:
    from aiohttp_client_cache.backends.gridfs import GridFSBackend
except ImportError as e:
    GridFSBackend = get_placeholder_backend(e)  # type: ignore
try:
    from aiohttp_client_cache.backends.mongo import MongoDBBackend
except ImportError as e:
    MongoDBBackend = get_placeholder_backend(e)  # type: ignore
try:
    from aiohttp_client_cache.backends.redis import RedisBackend
except ImportError as e:
    RedisBackend = get_placeholder_backend(e)  # type: ignore
try:
    from aiohttp_client_cache.backends.sqlite import SQLiteBackend
except ImportError as e:
    SQLiteBackend = get_placeholder_backend(e)  # type: ignore
