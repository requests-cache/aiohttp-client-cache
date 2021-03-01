import hashlib
import pickle
from abc import ABCMeta, abstractmethod
from collections import UserDict
from datetime import timedelta
from logging import getLogger
from typing import Callable, Iterable, Optional, Union
from urllib.parse import parse_qsl, urlparse, urlunparse

from aiohttp import ClientRequest, ClientResponse
from aiohttp.typedefs import StrOrURL

from aiohttp_client_cache.response import AnyResponse, CachedResponse

ResponseOrKey = Union[CachedResponse, None, bytes, str]
logger = getLogger(__name__)


class CacheBackend:
    """Base class for cache backends. This manages higher-level cache operations,
    including cache expiration, generating cache keys, and managing redirect history.

    If instantiated directly, ``CacheBackend`` will use a non-persistent in-memory cache.

    Lower-level storage operations are handled by :py:class:`.BaseCache`.
    To extend this with your own custom backend, implement one or more subclasses of
    :py:class:`.BaseCache` to use as :py:attr:`CacheBackend.responses` and
    :py:attr:`CacheBackend.response_aliases`.

    Args:
        cache_name: Cache prefix or namespace, depending on backend; see notes below
        expire_after: Number of hours after which a cache entry will expire; se ``None`` to
            never expire
        allowed_codes: Limit caching only for response with this codes
        allowed_methods: Cache only requests of this methods
        include_headers: Make request headers part of the cache key
        ignored_params: List of request parameters to be excluded from the cache key.
        filter_fn: function that takes a :py:class:`aiohttp.ClientResponse` object and
            returns a boolean indicating whether or not that response should be cached. Will be
            applied to both new and previously cached responses

    The ``cache_name`` parameter will be used as follows depending on the backend:

        * ``sqlite``: Cache filename prefix, e.g ``my_cache.sqlite``
        * ``mongodb``: Database name
        * ``redis``: Namespace, meaning all keys will be prefixed with ``'cache_name:'``

    Note on cache key parameters: Set ``include_get_headers=True`` if you want responses to be
    cached under different keys if they only differ by headers. You may also provide
    ``ignored_parameters`` to ignore specific request params. This is useful, for example, when
    requesting the same resource with different credentials or access tokens.
    """

    def __init__(
        self,
        cache_name: str = 'aiohttp-cache',
        expire_after: Union[int, timedelta] = None,
        allowed_codes: tuple = (200,),
        allowed_methods: tuple = ('GET', 'HEAD'),
        include_headers: bool = False,
        ignored_params: Iterable = None,
        filter_fn: Callable = lambda r: True,
    ):
        self.name = cache_name
        if expire_after is not None and not isinstance(expire_after, timedelta):
            expire_after = timedelta(seconds=expire_after)
        self.expire_after = expire_after
        self.allowed_codes = allowed_codes
        self.allowed_methods = allowed_methods
        self.filter_fn = filter_fn
        self.disabled = False

        # Allows multiple redirects or other aliased URLs to point to the same cached response
        self.redirects = DictCache()  # type: BaseCache
        self.responses = DictCache()  # type: BaseCache

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
        logger.debug(f'is_cacheable checks for response from {response.url}: {cache_criteria}')  # type: ignore
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
            if not await self.responses.contains(key):
                key = str(await self.redirects.read(key))
            response = await self.responses.read(key)
        except (KeyError, TypeError):
            logger.debug('No cached response found')
            return None
        if not isinstance(response, CachedResponse):
            logger.debug('Cached response is invalid')
            return None
        # If the item is expired or filtered out, delete it from the cache
        if not self.is_cacheable(response):
            logger.info('Cached response expired; deleting')
            await self.delete(key)
            return None

        logger.info(f'Cached response found for key: {key}')
        return response

    async def save_response(self, key: str, response: ClientResponse):
        """Save response to cache

        Args:
            key: Key for this response
            response: Response to save
        """
        if not self.is_cacheable(response):
            return
        logger.info(f'Saving response for key: {key}')

        cached_response = await CachedResponse.from_client_response(response, self.expire_after)
        await self.responses.write(key, cached_response)

        # Alias any redirect requests to the same cache key
        for r in response.history:
            await self.redirects.write(self.create_key(r.method, r.url), key)

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

    async def delete_url(self, url: str):
        """Delete cached response associated with `url`, along with its history (if applicable).
        Works only for GET requests.
        """
        await self.delete(self.create_key('GET', url))

    async def delete_expired_responses(self):
        """Deletes entries from cache with creation time older than ``expire_after``.
        **Note:** Also deletes any cache items that are filtered out according to ``filter_fn()``
        and filter parameters (``allowable_*``)
        """
        logger.info(f'Deleting all responses more than {self.expire_after} hours old')
        keys_to_delete = set()

        for key in await self.responses.keys():
            response = await self.get_response(key)
            if response and response.is_expired:
                keys_to_delete.add(key)

        logger.info(f'Deleting {len(keys_to_delete)} expired cache entries')
        for key in keys_to_delete:
            await self.delete(key)

    async def has_url(self, url: str) -> bool:
        """Returns `True` if cache has `url`, `False` otherwise. Works only for GET request urls"""
        key = self.create_key('GET', url)
        return await self.responses.contains(key) or await self.redirects.contains(key)

    def create_key(
        self,
        method: str,
        url: StrOrURL,
        params: dict = None,
        data: dict = None,
        headers: dict = None,
        **kwargs,
    ) -> str:
        """Create a unique cache key based on request details"""
        if self.ignored_params:
            url, params, body = self._remove_ignored_parameters(url, params, data)

        key = hashlib.sha256()
        key.update(method.upper().encode())
        key.update(str(url).encode())
        key.update(_encode_dict(params))
        key.update(_encode_dict(data))

        if (
            self.include_headers
            and headers is not None
            and headers != ClientRequest.DEFAULT_HEADERS
        ):
            for name, value in sorted(headers.items()):
                key.update(name.encode())
                key.update(value.encode())
        return key.hexdigest()

    def _remove_ignored_parameters(self, url, params, data):
        def filter_ignored_params(d):
            return {k: v for k, v in d.items() if k not in self.ignored_params}

        # Strip off any request params manually added to URL and add to `params`
        u = urlparse(url)
        if u.query:
            query = parse_qsl(u.query)
            params.update(query)
            url = urlunparse((u.scheme, u.netloc, u.path, u.params, [], u.fragment))

        params = filter_ignored_params(params)
        data = filter_ignored_params(data)
        return url, params, data


# TODO: Support yarl.URL like aiohttp does?
class BaseCache(metaclass=ABCMeta):
    """A wrapper for lower-level cache storage operations. This is separate from
    :py:class:`.CacheBackend` to allow a single backend to contain multiple cache objects.

    This is no longer using a dict-like interface due to lack of python syntax support for async
    dict operations.
    """

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
    async def keys(self) -> Iterable[str]:
        """Get all keys stored in the cache"""

    @abstractmethod
    async def read(self, key: str) -> ResponseOrKey:
        """Read a single item from the cache. Returns ``None`` if the item is missing."""

    @abstractmethod
    async def size(self) -> int:
        """Get the number of items in the cache"""

    @abstractmethod
    async def values(self) -> Iterable[ResponseOrKey]:
        """Get all values stored in the cache"""

    @abstractmethod
    async def write(self, key: str, item: ResponseOrKey):
        """Write an item to the cache"""

    @staticmethod
    def unpickle(result):
        return pickle.loads(bytes(result)) if result else None

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

    async def delete(self, key: str):
        del self.data[key]

    async def clear(self):
        self.data.clear()

    async def contains(self, key: str) -> bool:
        return key in self.data

    async def keys(self) -> Iterable[str]:  # type: ignore
        return self.data.keys()

    async def read(self, key: str) -> Union[CachedResponse, str]:
        return self.data[key]

    async def size(self) -> int:
        return len(self.data)

    async def values(self) -> Iterable[ResponseOrKey]:  # type: ignore
        return self.data.values()

    async def write(self, key: str, item: ResponseOrKey):
        self.data[key] = item


def _encode_dict(d):
    item_pairs = [f'{k}={v}' for k, v in sorted((d or {}).items())]
    return '&'.join(item_pairs).encode()
