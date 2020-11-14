"""Core functions for cache configuration"""
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Callable, Union

from aiohttp import ClientSession as OriginalSession
from aiohttp_client_cache import backends


class CachedSession(OriginalSession):
    """ :py:class:`.aiohttp.ClientSession` with caching support."""

    def __init__(
        self,
        cache_name: str = 'cache',
        backend: str = None,
        expire_after: Union[int, timedelta] = None,
        allowable_codes: tuple = (200,),
        allowable_methods: tuple = ('GET',),
        filter_fn: Callable = lambda r: True,
        **backend_options,
    ):
        """
        Args:
            cache_name: Cache prefix or namespace, depending on backend; see notes below
            backend: cache backend name; see see :ref:`persistence` for details. May also be a
                backend implementation subclassing :py:class:`.BaseCache`. Defaults to ``sqlite``
                if available, otherwise fallback to ``memory``
            expire_after: Number of seconds after cache will be expired, or ``None`` to never expire
            allowable_codes: Limit caching only for response with this codes
            allowable_methods: Cache only requests of this methods
            filter_fn: function that takes a :py:class:`aiohttp.ClientResponse` object and
                returns a boolean indicating whether or not that response should be cached. Will be
                applied to both new and previously cached responses
            include_get_headers: Make response headers part of the cache key
            ignored_parameters: List of request parameters to be excluded from the cache key.
            backend_options: Additional backend-specific options; see :py:module:`.backends` for details

        The ``cache_name`` parameter will be used as follows depending on the backend:

            * ``sqlite``: Cache filename prefix, e.g ``my_cache.sqlite``
            * ``mongodb``: Database name
            * ``redis``: Namespace, meaning all keys will be prefixed with ``'cache_name:'``

        Note on cache key parameters: Set ``include_get_headers=False`` if you want responses to be
        cached under the same key if they only differ by headers. You may also provide
        ``ignored_parameters`` to ignore specific request params. This is useful, for example, when
        requesting the same resource with different credentials or access tokens.
        """
        self.cache = backends.create_backend(backend, cache_name, expire_after, **backend_options)
        self._cache_name = cache_name
        self._cache_allowable_codes = allowable_codes
        self._cache_allowable_methods = allowable_methods
        self._filter_fn = filter_fn
        super().__init__()

    async def get(self, url: str, **kwargs):
        """Perform HTTP GET request."""
        return await self.request('GET', url, **kwargs)

    async def request(self, method, url, **kwargs):
        cache_key = self.cache.create_key(method, url, **kwargs)

        # Attempt to fetch cached response; if missing or expired, fetch new one
        response, timestamp = self.cache.get_response(cache_key)
        if response is None or response.is_expired:
            return await self.send_and_cache_request(method, url, cache_key, **kwargs)

        # TODO: Handle this in BaseCache
        # If the request is filtered out and has a previously cached response, delete it
        if getattr(response, "from_cache", False) and not self._filter_fn(response):
            self.cache.delete(cache_key)
            return response

        # Alias any redirect requests to the same cache key
        for r in response.history:
            self.cache.add_key_mapping(self.cache.create_key(r.request), cache_key)

        response.from_cache = True
        return response

    async def send_and_cache_request(self, method, url, cache_key, **kwargs):
        async with super().request(method, url, **kwargs) as response:
            await response.read()
        if response.status in self._cache_allowable_codes:
            self.cache.save_response(cache_key, response)
        response.from_cache = False
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
        self._is_cache_disabled = True
        try:
            yield
        finally:
            self._is_cache_disabled = False

    def remove_expired_responses(self):
        """Remove expired responses from storage"""
        self.cache.remove_expired_responses()

    def __repr__(self):
        return (
            f'<CachedSession({self.cache.__class__.__name__}("{self._cache_name}", ...), '
            f'expire_after={self._cache_expire_after}, '
            f'allowable_methods={self._cache_allowable_methods})>'
        )
