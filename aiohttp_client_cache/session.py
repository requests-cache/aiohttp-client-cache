"""Core functions for cache configuration"""
import warnings
from contextlib import asynccontextmanager
from logging import getLogger
from typing import TYPE_CHECKING, Optional, Tuple

from aiohttp import ClientSession
from aiohttp.typedefs import StrOrURL

from aiohttp_client_cache.backends import CacheBackend, get_valid_kwargs
from aiohttp_client_cache.cache_control import CacheActions, ExpirationTime, compose_refresh_headers
from aiohttp_client_cache.response import AnyResponse, CachedResponse, set_response_defaults
from aiohttp_client_cache.signatures import extend_signature

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
        cache: Optional[CacheBackend] = None,
        **kwargs,
    ):
        self.cache = cache or CacheBackend()

        # Pass along any valid kwargs for ClientSession (or custom session superclass)
        session_kwargs = get_valid_kwargs(super().__init__, {**kwargs, 'base_url': base_url})
        super().__init__(**session_kwargs)

    @extend_signature(ClientSession._request)
    async def _request(
        self,
        method: str,
        str_or_url: StrOrURL,
        expire_after: ExpirationTime = None,
        refresh: bool = False,
        **kwargs,
    ) -> AnyResponse:
        """Wrapper around :py:meth:`.SessionClient._request` that adds caching"""
        # Attempt to fetch cached response
        response, actions = await self.cache.request(
            method, str_or_url, expire_after=expire_after, refresh=refresh, **kwargs
        )

        def restore_cookies(r):
            self.cookie_jar.update_cookies(r.cookies or {}, r.url)
            for redirect in r.history:
                self.cookie_jar.update_cookies(redirect.cookies or {}, redirect.url)

        if actions.revalidate and response:
            from_cache, new_response = await self._refresh_cached_response(
                method, str_or_url, response, actions, **kwargs
            )
            if not from_cache:
                return set_response_defaults(new_response)
            else:
                restore_cookies(new_response)
                return new_response

        # Restore any cached cookies to the session
        if response:
            restore_cookies(response)
            return response
        # If the response was missing or expired, send and cache a new request
        else:
            if actions.skip_read:
                logger.debug(f'Reading from cache was skipped; making request to {str_or_url}')
            else:
                logger.debug(f'Cached response not found; making request to {str_or_url}')
            new_response = await super()._request(method, str_or_url, **kwargs)
            actions.update_from_response(new_response)
            if await self.cache.is_cacheable(new_response, actions):
                await self.cache.save_response(new_response, actions.key, actions.expires)
            return set_response_defaults(new_response)

    async def _refresh_cached_response(
        self,
        method: str,
        str_or_url: StrOrURL,
        cached_response: CachedResponse,
        actions: CacheActions,
        **kwargs,
    ) -> Tuple[bool, AnyResponse]:
        """Checks if the cached response is still valid using conditional requests if supported"""

        # check whether we can do a conditional request,
        # i.e. if the necessary headers are present (ETag, Last-Modified)
        conditional_request_supported, refresh_headers = compose_refresh_headers(
            kwargs.get('headers'), cached_response.headers
        )

        if conditional_request_supported:
            logger.debug(f'Refreshing cached response; making request to {str_or_url}')
            kwargs['headers'] = refresh_headers
            refreshed_response = await super()._request(method, str_or_url, **kwargs)

            if refreshed_response.status == 304:
                logger.debug('Cached response not modified; returning cached response')
                return True, cached_response
            else:
                actions.update_from_response(refreshed_response)
                if await self.cache.is_cacheable(refreshed_response, actions):
                    logger.debug('Cached response refreshed; updating cache')
                    await self.cache.save_response(refreshed_response, actions.key, actions.expires)
                else:
                    logger.debug('Cached response refreshed; deleting from cache')
                    await self.cache.delete(actions.key)

                return False, refreshed_response
        else:
            logger.debug(
                'Conditional requests not supported, no ETag or Last-Modified headers present; '
                'returning cached response'
            )
            return True, cached_response

    async def close(self):
        """Close both aiohttp connector and any backend connection(s) on contextmanager exit"""
        await super().close()
        await self.cache._close_if_enabled()

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
    warnings.simplefilter('ignore')

    class CachedSession(CacheMixin, ClientSession):
        """A drop-in replacement for :py:class:`aiohttp.ClientSession` that adds caching support

        Args:
            cache: A cache backend object. See :py:mod:`aiohttp_client_cache.backends` for
                options. If not provided, an in-memory cache will be used.
        """

        async def __aenter__(self) -> 'CachedSession':
            return self
