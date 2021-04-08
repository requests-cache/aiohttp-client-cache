import pickle
from abc import ABCMeta, abstractmethod
from collections import UserDict
from datetime import datetime
from logging import getLogger
from typing import AsyncIterable, Callable, Iterable, Optional, Union

from aiohttp import ClientResponse
from aiohttp.typedefs import StrOrURL

from aiohttp_client_cache.cache_keys import create_key
from aiohttp_client_cache.expiration import ExpirationPatterns, ExpirationTime, get_expiration
from aiohttp_client_cache.forge_utils import extend_init_signature
from aiohttp_client_cache.response import AnyResponse, CachedResponse

ResponseOrKey = Union[CachedResponse, bytes, str, None]
logger = getLogger(__name__)


class CacheBackend:
    """Base class for cache backends. This manages higher-level cache operations,
    including cache expiration, generating cache keys, and managing redirect history.

    If instantiated directly, ``CacheBackend`` will use a non-persistent in-memory cache.

    Lower-level storage operations are handled by :py:class:`.BaseCache`.
    To extend this with your own custom backend, implement one or more subclasses of
    :py:class:`.BaseCache` to use as :py:attr:`CacheBackend.responses` and
    :py:attr:`CacheBackend.response_aliases`.

    **Cache Name:**

    The ``cache_name`` parameter will be used as follows depending on the backend:

    * ``sqlite``: Cache filename prefix, e.g ``my_cache.sqlite``
    * ``mongodb``: Database name
    * ``redis``: Namespace, meaning all keys will be prefixed with ``'cache_name:'``

    **Cache Keys:**

    The cache key is a hash created from request information, and is used as an index for cached
    responses. There are a couple ways you can customize how the cache key is created:

    * Use ``include_get_headers`` if you want headers to be included in the cache key. In other
      words, this will create separate cache items for responses with different headers.
    * Use ``ignored_parameters`` to exclude specific request params from the cache key. This is
      useful, for example, if you request the same resource with different credentials or access
      tokens.

    **URL Patterns:**

    The ``urls_expire_after`` parameter can be used to set different expiration times for different
    requests, based on glob patterns. This allows you to customize caching based on what you
    know about what you're requesting. For example, you might request one resource that gets updated
    frequently, another that changes infrequently, and another that never changes.

    Example::

        urls_expire_after = {
            '*.site_1.com': timedelta(days=1),
            'site_2.com/resource_1': timedelta(hours=12),
            'site_2.com/resource_2': 60,
            'site_2.com/static': -1,
        }

    Notes:

    * ``urls_expire_after`` should be a dict in the format ``{'pattern': expiration_time}``
    * ``expiration_time`` may be either a number (in seconds) or a ``timedelta``
      (same as ``expire_after``)
    * Patterns will match request **base URLs**, so the pattern ``site.com/base`` is equivalent to
      ``https://site.com/base/**``
    * If there is more than one match, the first match (in the order they are defined) will be used
    * If no patterns match a request, ``expire_after`` will be used as a default.
    """

    def __init__(
        self,
        cache_name: str = 'aiohttp-cache',
        expire_after: ExpirationTime = -1,
        urls_expire_after: ExpirationPatterns = None,
        allowed_codes: tuple = (200,),
        allowed_methods: tuple = ('GET', 'HEAD'),
        include_headers: bool = False,
        ignored_params: Iterable = None,
        filter_fn: Callable = lambda r: True,
        **kwargs,
    ):
        """
        Args:
            cache_name: Cache prefix or namespace, depending on backend
            expire_after: Expiration time after which a cache entry will expire; may be a numeric value
                in seconds, a :py:class:`.timedelta`, or ``-1`` to never expire
            urls_expire_after: Expiration times to apply for different URL patterns
            allowed_codes: Only cache responses with these status codes
            allowed_methods: Only cache requests with these HTTP methods
            include_headers: Make request headers part of the cache key
            ignored_params: Request parameters to be excluded from the cache key
            filter_fn: function that takes a :py:class:`aiohttp.ClientResponse` object and
                returns a boolean indicating whether or not that response should be cached. Will be
                applied to both new and previously cached responses
        """
        self.name = cache_name
        self.expire_after = expire_after
        self.urls_expire_after = urls_expire_after
        self.allowed_codes = allowed_codes
        self.allowed_methods = allowed_methods
        self.filter_fn = filter_fn
        self.disabled = False

        # Allows multiple redirects or other aliased URLs to point to the same cached response
        self.redirects: BaseCache = DictCache()
        self.responses: BaseCache = DictCache()

        self.include_headers = include_headers
        self.ignored_params = set(ignored_params or [])

    def is_cacheable(self, response: Union[AnyResponse, None]) -> bool:
        """Perform all checks needed to determine if the given response should be cached"""
        if not response:
            return False
        cache_criteria = {
            'allowed method': response.method in self.allowed_methods,
            'allowed status': response.status in self.allowed_codes,
            'not disabled': not self.disabled,
            'not expired': not getattr(response, 'is_expired', False),
            'not filtered': self.filter_fn(response),
        }
        logger.debug(f'Pre-cache checks for response from {response.url}: {cache_criteria}')  # type: ignore
        return all(cache_criteria.values())

    async def get_response(self, key: str) -> Optional[CachedResponse]:
        """Retrieve response and timestamp for `key` if it's stored in cache,
        otherwise returns ``None```

        Args:
            key: key of resource
        """
        # Attempt to fetch response from the cache
        logger.debug(f'Attempting to get cached response for key: {key}')
        try:
            response = await self.responses.read(key) or await self._get_redirect_response(str(key))
        except (AttributeError, KeyError, TypeError, pickle.PickleError):
            response = None

        if not response:
            logger.debug('No cached response found')
        # If the item is expired or filtered out, delete it from the cache
        elif not self.is_cacheable(response):  # type: ignore
            logger.info('Cached response expired; deleting')
            response = None
            await self.delete(key)
        else:
            logger.info(f'Cached response found for key: {key}')

        # Response will be a CachedResponse or None by this point
        return response  # type: ignore

    async def _get_redirect_response(self, key: str) -> Optional[CachedResponse]:
        """Get the response referenced by a redirect key, if available"""
        redirect_key = await self.redirects.read(key)
        return await self.responses.read(redirect_key) if redirect_key else None  # type: ignore

    async def save_response(
        self, key: str, response: ClientResponse, expire_after: ExpirationTime = None
    ):
        """Save response to cache

        Args:
            key: Key for this response
            response: Response to save
            expire_after: Expiration time to set only for this request; overrides
                ``CachedSession.expire_after``, and accepts all the same values.
        """
        if not self.is_cacheable(response):
            return
        logger.info(f'Saving response for key: {key}')

        expire_after = self._get_expiration(response, expire_after)
        cached_response = await CachedResponse.from_client_response(response, expire_after)
        await self.responses.write(key, cached_response)

        # Alias any redirect requests to the same cache key
        for r in response.history:
            await self.redirects.write(self.create_key(r.method, r.url), key)

    def _get_expiration(
        self, response: ClientResponse, request_expire_after: ExpirationTime = None
    ) -> Optional[datetime]:
        """Get the appropriate expiration for the given response"""
        return get_expiration(
            response, request_expire_after, self.expire_after, self.urls_expire_after
        )

    async def clear(self):
        """Clear cache"""
        logger.info('Clearing cache')
        await self.responses.clear()
        await self.redirects.clear()

    async def delete(self, key: str):
        """Delete a response from the cache, along with its history (if applicable)"""

        async def delete_history(response):
            if not response:
                return
            for r in response.history:
                await self.redirects.delete(self.create_key(r.method, r.url))

        logger.debug(f'Deleting cached responses for key: {key}')
        redirect_key = str(await self.redirects.pop(key))
        await delete_history(await self.responses.pop(key))
        await delete_history(await self.responses.pop(redirect_key))

    async def delete_expired_responses(self):
        """Deletes all expired responses from the cache.
        Also deletes any cache items that are filtered out according to ``filter_fn()``.
        """
        logger.info('Deleting all expired responses')
        keys_to_delete = set()

        async for key in self.responses.keys():
            response = await self.responses.read(key)
            if response and response.is_expired or not self.filter_fn(response):
                keys_to_delete.add(key)

        logger.info(f'Deleting {len(keys_to_delete)} expired cache entries')
        for key in keys_to_delete:
            await self.delete(key)

    def create_key(self, *args, **kwargs):
        """Create a unique cache key based on request details"""
        return create_key(
            *args,
            include_headers=self.include_headers,
            ignored_params=self.ignored_params,
            **kwargs,
        )

    async def delete_url(self, url: StrOrURL):
        """Delete cached response associated with `url`, along with its history (if applicable).
        Works only for GET requests.
        """
        await self.delete(self.create_key('GET', url))

    async def has_url(self, url: StrOrURL) -> bool:
        """Returns `True` if cache has `url`, `False` otherwise. Works only for GET request urls"""
        key = self.create_key('GET', url)
        return await self.responses.contains(str(key)) or await self.redirects.contains(str(key))

    async def get_urls(self) -> AsyncIterable[str]:
        """Get all URLs currently in the cache"""
        async for r in self.responses.values():
            yield r.url  # type: ignore


# TODO: Support yarl.URL like aiohttp does?
class BaseCache(metaclass=ABCMeta):
    """A wrapper for lower-level cache storage operations. This is separate from
    :py:class:`.CacheBackend` to allow a single backend to contain multiple cache objects.
    """

    def __init__(
        self,
        secret_key: Union[Iterable, str, bytes] = None,
        salt: Union[str, bytes] = b'aiohttp-client-cache',
        serializer=None,
        **kwargs,
    ):
        """
        Args:
            secret_key: Optional secret key used to sign cache items for added security
            salt: Optional salt used to sign cache items
            serializer: Custom serializer that provides ``loads`` and ``dumps`` methods
        """
        super().__init__()
        self._serializer = serializer or self._get_serializer(secret_key, salt)

    def serialize(self, item: ResponseOrKey = None) -> Optional[bytes]:
        """Serialize a URL or response into bytes"""
        if isinstance(item, bytes):
            return item
        return self._serializer.dumps(item) if item else None

    def deserialize(self, item: ResponseOrKey) -> Union[CachedResponse, str, None]:
        """Deserialize a cached URL or response"""
        if isinstance(item, (CachedResponse, str)):
            return item
        return self._serializer.loads(item) if item else None

    # TODO: Remove once all backends have been updated to use serialize/deserialize
    @staticmethod
    def unpickle(result):
        return pickle.loads(bytes(result)) if result else None

    @staticmethod
    def _get_serializer(secret_key, salt):
        """Get the appropriate serializer to use; either ``itsdangerous``, if a secret key is
        specified, or plain ``pickle`` otherwise.
        Raises:
            py:exc:`ImportError` if ``secret_key`` is specified but ``itsdangerous`` is not installed
        """
        if secret_key:
            from itsdangerous.serializer import Serializer

            return Serializer(secret_key, salt=salt, serializer=pickle)
        else:
            return pickle

    @abstractmethod
    async def contains(self, key: str) -> bool:
        """Check if a key is stored in the cache"""

    @abstractmethod
    async def clear(self):
        """Delete all items from the cache"""

    @abstractmethod
    async def delete(self, key: str):
        """Delete a single item from the cache. Does not raise an error if the item is missing."""

    @abstractmethod
    def keys(self) -> AsyncIterable[str]:
        """Get all keys stored in the cache"""

    @abstractmethod
    async def read(self, key: str) -> ResponseOrKey:
        """Read a single item from the cache. Returns ``None`` if the item is missing."""

    @abstractmethod
    async def size(self) -> int:
        """Get the number of items in the cache"""

    @abstractmethod
    def values(self) -> AsyncIterable[ResponseOrKey]:
        """Get all values stored in the cache"""

    @abstractmethod
    async def write(self, key: str, item: ResponseOrKey):
        """Write an item to the cache"""

    async def pop(self, key: str, default=None) -> ResponseOrKey:
        """Delete an item from the cache, and return the deleted item"""
        try:
            item = await self.read(key)
            await self.delete(key)
            return item
        except KeyError:
            return default


CacheBackend = extend_init_signature(BaseCache)(CacheBackend)  # type: ignore


class DictCache(BaseCache, UserDict):
    """Simple in-memory storage that wraps a dict with the :py:class:`.BaseStorage` interface"""

    async def delete(self, key: str):
        try:
            del self.data[key]
        except KeyError:
            pass

    async def clear(self):
        self.data.clear()

    async def contains(self, key: str) -> bool:
        return key in self.data

    async def keys(self) -> AsyncIterable[str]:  # type: ignore
        for key in self.data.keys():
            yield key

    async def read(self, key: str) -> Union[CachedResponse, str, None]:
        try:
            return self.data[key]
        except KeyError:
            return None

    async def size(self) -> int:
        return len(self.data)

    async def values(self) -> AsyncIterable[ResponseOrKey]:  # type: ignore
        for value in self.data.values():
            yield value

    async def write(self, key: str, item: ResponseOrKey):
        self.data[key] = item
