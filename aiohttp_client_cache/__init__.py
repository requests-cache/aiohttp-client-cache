__version__ = '0.5.0'

# flake8: noqa: F401, F403
try:
    from aiohttp_client_cache.backends import *
    from aiohttp_client_cache.response import CachedResponse
    from aiohttp_client_cache.session import CachedSession
# When running setup.py outside a virtualenv
except ImportError:
    pass
