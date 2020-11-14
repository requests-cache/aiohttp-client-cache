"""Core functions for cache configuration"""
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Callable

from aiohttp import ClientSession as OriginalSession
from aiohttp_client_cache import backends


class CachedSession(OriginalSession):
    """ :py:class:`.aiohttp.ClientSession` with caching support."""

    def __init__(
        self,
        cache_name: str = 'cache',
        backend: str = None,
        expire_after: int = None,
        allowable_codes: tuple = (200,),
        allowable_methods: tuple = ('GET',),
        filter_fn: Callable = lambda r: True,
        **backend_options,
    ):
        """
        :param cache_name: for ``sqlite`` backend: cache file will start with this prefix,
                           e.g ``cache.sqlite``

                           for ``mongodb``: it's used as database name

                           for ``redis``: it's used as the namespace. This means all keys
                           are prefixed with ``'cache_name:'``
        :param backend: cache backend name e.g ``'sqlite'``, ``'mongodb'``, ``'redis'``, ``'memory'``.
                        (see :ref:`persistence`). Or instance of backend implementation.
                        Default value is ``None``, which means use ``'sqlite'`` if available,
                        otherwise fallback to ``'memory'``.
        :param expire_after: ``timedelta`` or number of seconds after cache will be expired
                             or `None` (default) to ignore expiration
        :param allowable_codes: limit caching only for response with this codes (default: 200)
        :param allowable_methods: cache only requests of this methods (default: 'GET')
        :param filter_fn: function to apply to each response; the response is only cached if
                          this returns `True`. Note that this function does not not modify
                          the cached response in any way.
        :kwarg backend_options: options for chosen backend. See corresponding
                                :ref:`sqlite <backends_sqlite>`, :ref:`mongo <backends_mongo>`
                                and :ref:`redis <backends_redis>` backends API documentation
        :param include_get_headers: If `True` headers will be part of cache key.
                                    E.g. after get('some_link', headers={'Accept':'application/json'})
                                    get('some_link', headers={'Accept':'application/xml'}) is not from cache.
        :param ignored_parameters: List of parameters to be excluded from the cache key.
                                   Useful when requesting the same resource through different
                                   credentials or access tokens, passed as parameters.
        """
        self.cache = backends.create_backend(backend, cache_name, backend_options)
        self._cache_name = cache_name

        if expire_after is not None and not isinstance(expire_after, timedelta):
            expire_after = timedelta(seconds=expire_after)
        self._cache_expire_after = expire_after

        self._cache_allowable_codes = allowable_codes
        self._cache_allowable_methods = allowable_methods
        self._filter_fn = filter_fn
        super().__init__()

    async def get(self, url: str, **kwargs):
        """Perform HTTP GET request."""
        return await self.request('GET', url, **kwargs)

    async def request(self, method, url, **kwargs):
        cache_key = self.cache.create_key(method, url, **kwargs)

        # Attempt to fetch cached response; if expired, delete it and fetch new one
        response, timestamp = self.cache.get_response_and_time(cache_key)
        if response is None or self._is_expired(timestamp):
            self.cache.delete(cache_key)
            return await self.send_and_cache_request(method, url, cache_key, **kwargs)

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

    def _is_expired(self, timestamp):
        time_elapsed = datetime.utcnow() - timestamp
        return self._cache_expire_after and time_elapsed >= self._cache_expire_after

    @contextmanager
    def cache_disabled(self):
        """
        Context manager for temporary disabling cache
        ::

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
        """Removes expired responses from storage"""
        if not self._cache_expire_after:
            return
        self.cache.remove_old_entries(datetime.utcnow() - self._cache_expire_after)

    def __repr__(self):
        return "<CachedSession(%s('%s', ...), expire_after=%s, " "allowable_methods=%s)>" % (
            self.cache.__class__.__name__,
            self._cache_name,
            self._cache_expire_after,
            self._cache_allowable_methods,
        )
