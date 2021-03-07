import hashlib
import pickle
from abc import ABCMeta, abstractmethod
from collections import UserDict
from datetime import datetime, timedelta
from fnmatch import fnmatch as glob_match
from logging import getLogger
from typing import Callable, Dict, Iterable, Optional, Union
from urllib.parse import parse_qsl, urlparse, urlsplit, urlunparse

from aiohttp import ClientRequest, ClientResponse
from aiohttp.typedefs import StrOrURL

from aiohttp_client_cache.response import AnyResponse, CachedResponse

ResponseOrKey = Union[CachedResponse, bytes, str, None]
ExpirationPatterns = Dict[str, Optional[timedelta]]
ExpirationTime = Union[int, float, timedelta, None]
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
        cache_name: Cache prefix or namespace, depending on backend (see notes below)
        expire_after: Expiration time, in hours, after which a cache entry will expire;
            set to ``None`` to never expire
        expire_after_urls: Expiration times to apply for different URL patterns (see notes below)
        allowed_codes: Only cache responses with these status codes
        allowed_methods: Only cache requests with these HTTP methods
        include_headers: Make request headers part of the cache key (see notes below)
        ignored_params: Request parameters to be excluded from the cache key (see notes below)
        filter_fn: function that takes a :py:class:`aiohttp.ClientResponse` object and
            returns a boolean indicating whether or not that response should be cached. Will be
            applied to both new and previously cached responses

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

    The ``expire_after_urls`` parameter can be used to set different expiration times for different
    requests, based on glob patterns. This allows you to customize caching based on what you
    know about what you're requesting. For example, you might request one resource that gets updated
    frequently, another that changes infrequently, and another that never changes.

    Example::

        expire_after_urls = {
            '*.site_1.com': 24,
            'site_2.com/resource_1': 24 * 2,
            'site_2.com/resource_2': 24 * 7,
            'site_2.com/static': None,
        }

    Notes:

    * ``expire_after_urls`` should be a dict in the format ``{'pattern': expiration_time}``
    * ``expiration_time`` may be either a number (in hours) or a ``timedelta``
      (same as ``expire_after``)
    * Patterns will match request **base URLs**, so the pattern ``site.com/base`` is equivalent to
      ``https://site.com/base/**``
    * If there is more than one match, the first match (in the order they are defined) will be used
    * If no patterns match a request, ``expire_after`` will be used as a default.

    """

    def __init__(
        self,
        cache_name: str = 'aiohttp-cache',
        expire_after: ExpirationTime = None,
        expire_after_urls: Dict[str, ExpirationTime] = None,
        allowed_codes: tuple = (200,),
        allowed_methods: tuple = ('GET', 'HEAD'),
        include_headers: bool = False,
        ignored_params: Iterable = None,
        filter_fn: Callable = lambda r: True,
    ):
        self.name = cache_name
        self.expire_after = _convert_timedelta(expire_after)
        self.expire_after_urls: ExpirationPatterns = {
            _format_pattern(k): _convert_timedelta(v) for k, v in (expire_after_urls or {}).items()
        }
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

    def get_expiration_date(self, response: ClientResponse) -> Optional[datetime]:
        """Get the absolute expiration time for a response, applying URL patterns if available"""
        try:
            expire_after = self._get_expiration_for_url(response)
        except Exception:
            expire_after = self.expire_after
        return None if expire_after is None else datetime.utcnow() + expire_after

    def _get_expiration_for_url(self, response: ClientResponse) -> Optional[timedelta]:
        """Get the relative expiration time matching the specified URL, if any. If there is no
        match, raise a ``ValueError`` to differentiate beween this case and a matching pattern with
        ``expire_after=None``
        """
        for pattern, expire_after in self.expire_after_urls.items():
            if glob_match(_base_url(response.url), pattern):
                logger.debug(f'URL {response.url} matched pattern "{pattern}": {expire_after}')
                return expire_after
        raise ValueError('No matching URL pattern')

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

        # Update last_used time
        response.last_used = datetime.utcnow()
        await self.responses.write(key, response)

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

        expires = self.get_expiration_date(response)
        cached_response = await CachedResponse.from_client_response(response, expires)
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

    async def delete_url(self, url: StrOrURL):
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

    async def has_url(self, url: StrOrURL) -> bool:
        """Returns `True` if cache has `url`, `False` otherwise. Works only for GET request urls"""
        key = self.create_key('GET', url)
        return await self.responses.contains(str(key)) or await self.redirects.contains(str(key))

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


def _base_url(url: StrOrURL) -> str:
    url = str(url)
    return url.replace(urlsplit(url).scheme + '://', '')


def _convert_timedelta(expire_after: ExpirationTime = None) -> Optional[timedelta]:
    if expire_after is not None and not isinstance(expire_after, timedelta):
        expire_after = timedelta(hours=expire_after)
    return expire_after


def _encode_dict(d):
    item_pairs = [f'{k}={v}' for k, v in sorted((d or {}).items())]
    return '&'.join(item_pairs).encode()


def _format_pattern(pattern: str) -> str:
    """Add recursive wildcard to a glob pattern, to ensure it matches base URLs"""
    return pattern.rstrip('*') + '**'
