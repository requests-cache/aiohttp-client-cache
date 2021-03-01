__version__ = '0.2.0'

try:
    from aiohttp_client_cache.backends import *  # noqa
    from aiohttp_client_cache.response import CachedResponse  # noqa
    from aiohttp_client_cache.session import CachedSession  # noqa
# When running setup.py outside a virtualenv
except ImportError:
    pass
