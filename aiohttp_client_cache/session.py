"""Core functions for cache configuration"""
import warnings
from contextlib import asynccontextmanager
from logging import getLogger
from typing import TYPE_CHECKING, Optional

from aiohttp import ClientSession
from aiohttp.typedefs import StrOrURL

from aiohttp_client_cache.backends import CacheBackend, get_valid_kwargs
from aiohttp_client_cache.docs import copy_signature, extend_signature
from aiohttp_client_cache.response import AnyResponse, set_response_defaults

if TYPE_CHECKING:
    MIXIN_BASE = ClientSession
else:
    MIXIN_BASE = object

logger = getLogger(__name__)


class CacheMixin(MIXIN_BASE):
    """A mixin class for :py:class:`aiohttp.ClientSession` that adds caching support"""

    @extend_signature(ClientSession.__init__)
    def __init__(
        self,
        base_url: Optional[StrOrURL] = None,
        *,
        cache: CacheBackend = None,
        **kwargs,
    ):
        self.cache = cache or CacheBackend()

        # Pass along any valid kwargs for ClientSession (or custom session superclass)
        session_kwargs = get_valid_kwargs(super().__init__, {**kwargs, 'base_url': base_url})
        super().__init__(**session_kwargs)

    @copy_signature(ClientSession._request)
    async def _request(self, method: str, str_or_url: StrOrURL, **kwargs) -> AnyResponse:
        """Wrapper around :py:meth:`.SessionClient._request` that adds caching"""
        # Attempt to fetch cached response
        response, actions = await self.cache.request(method, str_or_url, **kwargs)

        # Restore any cached cookies to the session
        if response:
            self.cookie_jar.update_cookies(response.cookies or {}, response.url)
            for redirect in response.history:
                self.cookie_jar.update_cookies(redirect.cookies or {}, redirect.url)
            return response
        # If the response was missing or expired, send and cache a new request
        else:
            logger.debug(f'Cached response not found; making request to {str_or_url}')
            new_response = await super()._request(method, str_or_url, **kwargs)  # type: ignore
            actions.update_from_response(new_response)
            if await self.cache.is_cacheable(new_response, actions):
                await self.cache.save_response(new_response, actions.key, actions.expires)
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
