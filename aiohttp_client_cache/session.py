"""Core functions for cache configuration"""
from contextlib import contextmanager
from datetime import timedelta
from typing import Any, Callable, Union, Optional

from aiohttp import ClientSession
from aiohttp.typedefs import StrOrURL
from aiohttp_client_cache.backends import create_backend


class CachedSession(ClientSession):
    """ :py:class:`.aiohttp.ClientSession` with caching support."""

    def __init__(
        self,
        cache_name: str = 'http-cache',
        backend: str = None,
        expire_after: Union[int, timedelta] = None,
        allowable_codes: tuple = (200,),
        allowable_methods: tuple = ('GET',),
        filter_fn: Callable = lambda r: True,
        include_get_headers: bool = False,
        ignored_parameters: bool = None,
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
            allowable_codes: Limit caching only for response with this codes
            allowable_methods: Cache only requests of this methods
            include_get_headers: Make response headers part of the cache key
            ignored_parameters: List of request parameters to be excluded from the cache key.
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
        self.cache = create_backend(
            backend,
            cache_name,
            expire_after,
            filter_fn=filter_fn,
            allowable_codes=allowable_codes,
            allowable_methods=allowable_methods,
            include_get_headers=include_get_headers,
            ignored_parameters=ignored_parameters,
            **backend_options,
        )
        super().__init__()

    async def get(self, url: StrOrURL, **kwargs):
        """Perform an HTTP GET request"""
        return await self.request('GET', url, **kwargs)

    async def head(self, url: StrOrURL, **kwargs):
        """Perform an HTTP HEAD request"""
        return await self.request('GET', url, **kwargs)

    async def post(self, url: StrOrURL, data: Any = None, **kwargs):
        """Perform an HTTP POST request"""
        return await self.request('GET', url, data=data, **kwargs)

    async def put(self, url: StrOrURL, data: Any = None, **kwargs):
        """Perform an HTTP PUT request"""
        return await self.request('GET', url, data=data, **kwargs)

    async def patch(self, url: StrOrURL, data: Any = None, **kwargs):
        """Perform an HTTP PATCH request"""
        return await self.request('GET', url, data=data, **kwargs)

    async def delete(self, url: StrOrURL, **kwargs):
        """Perform an HTTP DELETE request"""
        return await self.request('GET', url, **kwargs)

    async def request(self, method, url, **kwargs):
        cache_key = self.cache.create_key(method, url, **kwargs)

        # Attempt to fetch cached response; if missing or expired, fetch new one
        response = await self.cache.get_response(cache_key)
        if response is None or getattr(response, 'is_expired', False):
            async with super().request(method, url, **kwargs) as response:
                await response.read()
            await self.cache.save_response(cache_key, response)

        return response

    @contextmanager
    def cache_disabled(self):
        """
        Context manager for temporarily disabling cache

        Example:

            >>> s = CachedSession()
            >>> with s.cache_disabled():
            ...     s.get('http://httpbin.org/ip')

        """
        self.cache.disabled = True
        yield
        self.cache.disabled = False

    async def delete_expired_responses(self):
        """Remove expired responses from storage"""
        await self.cache.delete_expired_responses()
