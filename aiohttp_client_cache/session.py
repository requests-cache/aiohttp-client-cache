"""Core functions for cache configuration"""
from contextlib import contextmanager
from datetime import timedelta
from typing import Callable, Iterable, Union

import forge
from aiohttp import ClientSession
from aiohttp.typedefs import StrOrURL

from aiohttp_client_cache.backends import init_backend
from aiohttp_client_cache.response import AnyResponse


class CacheMixin:
    """A mixin class for :py:class:`aiohttp.ClientSession` that adds caching support"""

    def __init__(
        self,
        cache_name: str = 'http-cache',
        backend: str = None,
        expire_after: Union[int, timedelta] = None,
        allowed_codes: tuple = (200,),
        allowed_methods: tuple = ('GET', 'HEAD'),
        filter_fn: Callable = lambda r: True,
        include_headers: bool = False,
        ignored_params: Iterable = None,
        **backend_options,
    ):
        """
        Args:
            cache_name: Cache prefix or namespace, depending on backend; see notes below
            backend: cache backend name; see see :ref:`persistence` for details. May also be a
                backend implementation subclassing :py:class:`.BaseCache`. Defaults to ``sqlite``
                if available, otherwise fallback to ``memory``
            expire_after: Number of hours after which a cache entry will expire; se ``None`` to
                never expire
            filter_fn: function that takes a :py:class:`aiohttp.ClientResponse` object and
                returns a boolean indicating whether or not that response should be cached. Will be
                applied to both new and previously cached responses
            allowed_codes: Limit caching only for response with this codes
            allowed_methods: Cache only requests of this methods
            include_headers: Make request headers part of the cache key
            ignored_params: List of request parameters to be excluded from the cache key.
            backend_options: Additional backend-specific options; see :py:module:`.backends` for details

        The ``cache_name`` parameter will be used as follows depending on the backend:

            * ``sqlite``: Cache filename prefix, e.g ``my_cache.sqlite``
            * ``mongodb``: Database name
            * ``redis``: Namespace, meaning all keys will be prefixed with ``'cache_name:'``

        Note on cache key parameters: Set ``include_get_headers=True`` if you want responses to be
        cached under different keys if they only differ by headers. You may also provide
        ``ignored_parameters`` to ignore specific request params. This is useful, for example, when
        requesting the same resource with different credentials or access tokens.
        """
        self.cache = init_backend(
            backend,
            cache_name,
            expire_after=expire_after,
            filter_fn=filter_fn,
            allowable_codes=allowed_codes,
            allowable_methods=allowed_methods,
            include_headers=include_headers,
            ignored_params=ignored_params,
            **backend_options,
        )
        super().__init__()

    @forge.copy(ClientSession._request)
    async def _request(self, method: str, str_or_url: StrOrURL, **kwargs) -> AnyResponse:
        """Wrapper around :py:meth:`.SessionClient._request` that adds caching"""
        cache_key = self.cache.create_key(method, str_or_url, **kwargs)

        # Attempt to fetch cached response; if missing or expired, fetch new one
        cached_response = await self.cache.get_response(cache_key)
        if cached_response and not getattr(cached_response, 'is_expired', False):
            return cached_response
        else:
            new_response = await super()._request(method, str_or_url, **kwargs)  # type: ignore
            await new_response.read()
            await self.cache.save_response(cache_key, new_response)
            return new_response

    @contextmanager
    def disable_cache(self):
        """Temporarily disable the cache

        Example:

            >>> session = CachedSession()
            >>> await session.get('http://httpbin.org/ip')
            >>> with session.disable_cache():
            >>>     # Will return a new response, not a cached one
            >>>     await session.get('http://httpbin.org/ip')
        """
        self.cache.disabled = True
        yield
        self.cache.disabled = False

    async def delete_expired_responses(self):
        """Remove all expired responses from the cache"""
        await self.cache.delete_expired_responses()


class CachedSession(ClientSession, CacheMixin):
    """A drop-in replacement for :py:class:`aiohttp.ClientSession` that adds caching support"""
