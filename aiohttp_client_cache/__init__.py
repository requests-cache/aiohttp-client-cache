__version__ = '0.1.0'

try:
    from aiohttp_client_cache.session import CachedSession
    from aiohttp_client_cache.response import CachedResponse
    from aiohttp_client_cache.backends import *
# When running setup.py outside a virtualenv
except ImportError:
    pass
