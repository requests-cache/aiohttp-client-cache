from __future__ import annotations

import inspect
import pickle
from abc import ABCMeta, abstractmethod
from collections import UserDict
from datetime import datetime
from logging import getLogger
from typing import Any, AsyncIterable, Awaitable, Callable, Iterable, Union

from aiohttp import ClientResponse
from aiohttp.typedefs import StrOrURL

from aiohttp_client_cache.cache_control import CacheActions, ExpirationPatterns, ExpirationTime
from aiohttp_client_cache.cache_keys import create_key
from aiohttp_client_cache.response import AnyResponse, CachedResponse

ResponseOrKey = Union[CachedResponse, bytes, str, None]
_FilterFn = Union[
    Callable[[AnyResponse], bool],
    Callable[[AnyResponse], Awaitable[bool]],
]

logger = getLogger(__name__)


class CacheBackend:
    """Base class for cache backends; includes a non-persistent, in-memory cache.

    This manages higher-level cache operations, including cache expiration, generating cache keys,
    and managing redirect history.

    Lower-level storage operations are handled by :py:class:`.BaseCache`.
    To extend this with your own custom backend, implement one or more subclasses of
    :py:class:`.BaseCache` to use as :py:attr:`CacheBackend.responses` and
    :py:attr:`CacheBackend.response_aliases`.
    """

    def __init__(
        self,
        cache_name: str = 'aiohttp-cache',
        expire_after: ExpirationTime = -1,
        urls_expire_after: ExpirationPatterns | None = None,
        allowed_codes: tuple[int, ...] = (200,),
        allowed_methods: tuple[str, ...] = ('GET', 'HEAD'),
        include_headers: bool = False,
        ignored_params: Iterable[str] | None = None,
        autoclose: bool = False,
        cache_control: bool = False,
        filter_fn: _FilterFn = lambda r: True,
        **kwargs: Any,
    ):
        """
        Args:
            cache_name: Cache prefix or namespace, depending on backend
            expire_after: Time after which a cache entry will be expired; see
                :ref:`user_guide:cache expiration` for possible formats
            urls_expire_after: Expiration times to apply for different URL patterns
            allowed_codes: Only cache responses with these status codes
            allowed_methods: Only cache requests with these HTTP methods
            include_headers: Cache requests with different headers separately
            ignored_params: Request parameters to be excluded from the cache key
            autoclose: Close any active backend connections when the session is closed
            cache_control: Use Cache-Control response headers
            filter_fn: function that takes a :py:class:`aiohttp.ClientResponse` object and
                returns a boolean indicating whether or not that response should be cached. Will be
                applied to both new and previously cached responses
        """
        self.name = cache_name
        self.expire_after = expire_after
        self.urls_expire_after = urls_expire_after
        self.allowed_codes = allowed_codes
        self.allowed_methods = allowed_methods
        self.cache_control = cache_control
        self.filter_fn = filter_fn
        self.autoclose = autoclose
        self.disabled = False

        # Allows multiple redirects or other aliased URLs to point to the same cached response
        self.redirects: BaseCache = DictCache()
        self.responses: BaseCache = DictCache()

        self.include_headers = include_headers
        self.ignored_params = set(ignored_params or [])

    async def is_cacheable(
        self, response: AnyResponse | None, actions: CacheActions | None = None
    ) -> bool:
        """Perform all checks needed to determine if the given response should be cached"""
        if not response:
            return False

        cache_criteria = {
            'disabled cache': self.disabled,
            'disabled method': str(response.method) not in self.allowed_methods,
            'disabled status': response.status not in self.allowed_codes,
            'disabled by filter': not (
                await self.filter_fn(response)
                if inspect.iscoroutinefunction(self.filter_fn)
                else self.filter_fn(response)
            ),
            'disabled by headers or expiration params': actions and actions.skip_write,
            'expired': getattr(response, 'is_expired', False),
        }
        logger.debug(f'Pre-cache checks for response from {response.url}: {cache_criteria}')
        return not any(cache_criteria.values())

    def create_cache_actions(
        self,
        key: str,
        url: StrOrURL,
        expire_after: ExpirationTime = None,
        refresh: bool = False,
        **kwargs,
    ) -> CacheActions:
        """Create cache actions based on request info

        Args:
            key: key from create_key function
            url: Request URL
            expire_after: Expiration time to set only for this request; overrides
                ``CachedSession.expire_after``, and accepts all the same values.
            refresh: Revalidate with the server before using a cached response, and refresh if needed
                (e.g., a "soft refresh", like F5 in a browser)
            kwargs: All other request arguments
        """
        return CacheActions.from_request(
            key,
            url=url,
            request_expire_after=expire_after,
            refresh=refresh,
            session_expire_after=self.expire_after,
            urls_expire_after=self.urls_expire_after,
            cache_control=self.cache_control,
            cache_disabled=self.disabled,
            **kwargs,
        )

    async def request(
        self,
        actions: CacheActions,
    ) -> CachedResponse | None:
        """Fetch a cached response based on cache actions

        Args:
            actions: CacheActions from create_cache_actions function
        """
        # Skip reading from the cache, if specified by request headers
        response = None if actions.skip_read else await self.get_response(actions.key)
        return response

    async def get_response(self, key: str) -> CachedResponse | None:
        """Fetch a cached response based on a cache key"""
        # Attempt to fetch the cached response
        logger.debug(f'Attempting to get cached response for key: {key}')
        try:
            response = await self.responses.read(key) or await self._get_redirect_response(str(key))
            # Catch "quiet" deserialization errors due to upgrading attrs
            if response is not None:
                assert response.method  # type: ignore
        except (AssertionError, AttributeError, KeyError, TypeError, pickle.PickleError):
            response = None

        if not response:
            logger.debug('No cached response found')
        # If the item is expired or filtered out, delete it from the cache
        elif not await self.is_cacheable(response):  # type: ignore
            logger.debug('Cached response expired; deleting')
            response = None
            await self.delete(key)
        else:
            logger.debug(f'Cached response found for key: {key}')

        # Response will be a CachedResponse or None by this point
        return response  # type: ignore

    async def _get_redirect_response(self, key: str) -> CachedResponse | None:
        """Get the response referenced by a redirect key, if available"""
        redirect_key = await self.redirects.read(key)
        return await self.responses.read(redirect_key) if redirect_key else None  # type: ignore

    async def save_response(
        self,
        response: ClientResponse,
        cache_key: str | None = None,
        expires: datetime | None = None,
    ):
        """Save a response to the cache

        Args:
            response: Response to save
            cache_key: Cache key to use for the response; will be generated if not provided
            expires: Expiration time to set for the response
        """
        cache_key = cache_key or self.create_key(response.method, response.url)
        cached_response = await CachedResponse.from_client_response(response, expires)
        await self.responses.write(cache_key, cached_response)

        # Alias any redirect requests to the same cache key
        for r in response.history:
            await self.redirects.write(self.create_key(r.method, r.url), cache_key)

    async def clear(self):
        """Clear cache"""
        logger.info('Clearing cache')
        await self.responses.clear()
        await self.redirects.clear()

    async def bulk_delete(self, keys: set):
        for key in keys:
            await self.delete(key)

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
            if response and response.is_expired or not self.filter_fn(response):  # type: ignore[union-attr,arg-type]
                keys_to_delete.add(key)

        logger.debug(f'Deleting {len(keys_to_delete)} expired cache entries')
        await self.bulk_delete(keys_to_delete)

    def create_key(self, method: str, url: StrOrURL, **kwargs: Any):
        """Create a unique cache key based on request details"""
        return create_key(
            method,
            url,
            include_headers=self.include_headers,
            ignored_params=self.ignored_params,
            **kwargs,
        )

    async def delete_url(self, url: StrOrURL, method: str = 'GET', **kwargs: Any):
        """Delete cached response associated with `url`, along with its history (if applicable)"""
        key = self.create_key(url=url, method=method, **kwargs)
        await self.delete(key)

    async def has_url(self, url: StrOrURL, method: str = 'GET', **kwargs) -> bool:
        """Returns `True` if cache has `url`, `False` otherwise"""
        key = self.create_key(method=method, url=url, **kwargs)
        return await self.responses.contains(str(key)) or await self.redirects.contains(str(key))

    async def get_urls(self) -> AsyncIterable[str]:
        """Get all URLs currently in the cache"""
        async for r in self.responses.values():
            yield r.url  # type: ignore

    async def close(self):
        """Close any active connections, if applicable"""
        await self.responses.close()
        await self.redirects.close()

    async def _close_if_enabled(self):
        """Close any active connections, if ``autoclose`` is enabled"""
        if self.autoclose:
            await self.close()


# TODO: Support yarl.URL like aiohttp does?
# TODO: Implement __aiter__?
class BaseCache(metaclass=ABCMeta):
    """A wrapper for lower-level cache storage operations. This is separate from
    :py:class:`.CacheBackend` to allow a single backend to contain multiple cache objects.

    Args:
        secret_key: Optional secret key used to sign cache items for added security
        salt: Optional salt used to sign cache items
        serializer: Custom serializer that provides ``loads`` and ``dumps`` methods
    """

    def __init__(
        self,
        secret_key: Iterable | str | bytes | None = None,
        salt: str | bytes = b'aiohttp-client-cache',
        serializer=None,
        **kwargs,
    ):
        super().__init__()
        self._serializer = serializer or self._get_serializer(secret_key, salt)

    def serialize(self, item: ResponseOrKey = None) -> bytes | None:
        """Serialize a URL or response into bytes"""
        if isinstance(item, bytes):
            return item
        return self._serializer.dumps(item) if item else None

    def deserialize(self, item: ResponseOrKey) -> CachedResponse | str | None:
        """Deserialize a cached URL or response"""
        if isinstance(item, (CachedResponse, str)):
            return item
        return self._serializer.loads(item) if item else None

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

    async def close(self):
        """Close any active connections, if applicable"""

    @abstractmethod
    async def delete(self, key: str):
        """Delete an item from the cache. Does not raise an error if the item is missing."""

    @abstractmethod
    async def bulk_delete(self, keys: set):
        """Delete item(s) from the cache. Does not raise an error if the item is missing."""

    @abstractmethod
    def keys(self) -> AsyncIterable[str]:
        """Get all keys stored in the cache"""

    @abstractmethod
    async def read(self, key: str) -> ResponseOrKey:
        """Read an item from the cache. Returns ``None`` if the item is missing."""

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


class DictCache(BaseCache, UserDict):
    """Simple in-memory storage that wraps a dict with the :py:class:`.BaseStorage` interface"""

    async def bulk_delete(self, keys: set):
        for key in keys:
            await self.delete(key)

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

    async def read(self, key: str) -> CachedResponse | str | None:
        """An additional step is needed here for response data. The original response object
        is still in memory, and hasn't gone through a serialize/deserialize loop. So, the file-like
        response body has already been read, and needs to be reset.
        """
        try:
            item = self.data[key]
        except KeyError:
            return None

        try:
            item.reset()
        except AttributeError:
            pass
        return item

    async def size(self) -> int:
        return len(self.data)

    async def values(self) -> AsyncIterable[ResponseOrKey]:  # type: ignore
        for value in self.data.values():
            yield value

    async def write(self, key: str, item: ResponseOrKey):
        self.data[key] = item
