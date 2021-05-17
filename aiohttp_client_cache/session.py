"""Core functions for cache configuration"""
import warnings
from contextlib import asynccontextmanager
from logging import getLogger

from aiohttp import ClientSession
from aiohttp.typedefs import StrOrURL

from aiohttp_client_cache.backends import CacheBackend
from aiohttp_client_cache.docs import copy_signature, extend_signature
from aiohttp_client_cache.expiration import ExpirationTime
from aiohttp_client_cache.response import AnyResponse, set_response_defaults

logger = getLogger(__name__)


class CacheMixin:
    """A mixin class for :py:class:`aiohttp.ClientSession` that adds caching support"""

    @extend_signature(ClientSession.__init__)
    def __init__(self, *, cache: CacheBackend = None, **kwargs):
        super().__init__(**kwargs)  # type: ignore
        self.cache = cache or CacheBackend()

    @copy_signature(ClientSession._request)
    async def _request(
        self, method: str, str_or_url: StrOrURL, expire_after: ExpirationTime = None, **kwargs
    ) -> AnyResponse:
        """Wrapper around :py:meth:`.SessionClient._request` that adds caching"""
        cache_key = self.cache.create_key(method, str_or_url, **kwargs)

        # Attempt to fetch cached response; if missing or expired, fetch new one
        cached_response = await self.cache.get_response(cache_key)
        if cached_response:
            return cached_response
        else:
            logger.info(f'Cached response not found; making request to {str_or_url}')
            new_response = await super()._request(method, str_or_url, **kwargs)  # type: ignore
            await new_response.read()
            await self.cache.save_response(cache_key, new_response, expire_after=expire_after)
            return set_response_defaults(new_response)

    @asynccontextmanager
    async def disabled(self):
        """Temporarily disable the cache

        Example:

            >>> async with CachedSession() as session:
            >>>     await session.get('http://httpbin.org/ip')
            >>>     async with session.disabled():
            >>>         # Will return a new response, not a cached one
            >>>         await session.get('http://httpbin.org/ip')
        """
        self.cache.disabled = True
        yield
        self.cache.disabled = False

    async def delete_expired_responses(self):
        """Remove all expired responses from the cache"""
        await self.cache.delete_expired_responses()


# Ignore aiohttp warning: "Inheritance from ClientSession is discouraged"
# Since only _request() is overridden, there is minimal chance of breakage, but still possible
with warnings.catch_warnings():
    warnings.simplefilter("ignore")

    class CachedSession(CacheMixin, ClientSession):
        """A drop-in replacement for :py:class:`aiohttp.ClientSession` that adds caching support

        Args:
            cache: A cache backend object. See :py:mod:`aiohttp_client_cache.backends` for
                options. If not provided, an in-memory cache will be used.
        """
