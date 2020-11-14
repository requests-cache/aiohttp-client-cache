__version__ = '0.6'

try:
    from aiohttp_client_cache.core import CachedSession
# When running setup.py outside a virtualenv
except ImportError:
    pass
