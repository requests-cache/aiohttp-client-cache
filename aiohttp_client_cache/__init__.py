__version__ = '0.6.0'

try:
    from aiohttp_client_cache.core import CachedSession
    from aiohttp_client_cache.cached_response import CachedResponse
    from aiohttp_client_cache.backends import *
# When running setup.py outside a virtualenv
except ImportError:
    pass
