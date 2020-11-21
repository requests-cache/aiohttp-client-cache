import hashlib
from abc import ABCMeta, abstractmethod
from collections import UserDict
from datetime import datetime, timedelta
from logging import getLogger
from typing import Iterable, Optional, Union
from urllib.parse import parse_qsl, urlparse, urlunparse

from aiohttp import ClientRequest, ClientResponse
from aiohttp.typedefs import StrOrURL

from aiohttp_client_cache.response import AnyResponse, CachedResponse

ResponseOrKey = Union[CachedResponse, str]
logger = getLogger(__name__)


class BaseCache:
    """Base class for cache implementations. Handles cache expiration and generating cache keys.
    Storage operations are handled by :py:class:`.BaseStorage`.

    To extend this with your own custom backend, implement a subclass of :py:class:`.BaseStorage`
    to use as :py:attr:`responses` and :py:attr:`response_aliases`.
    """

    def __init__(
        self,
        cache_name,
        expire_after,
        filter_fn=None,
        allowable_codes=None,
        allowable_methods=None,
        include_get_headers=False,
        ignored_parameters=None,
        **kwargs,
    ):
        self.name = cache_name
        if expire_after is not None and not isinstance(expire_after, timedelta):
            expire_after = timedelta(seconds=expire_after)
        self.expire_after = expire_after
        self.allowable_codes = allowable_codes
        self.allowable_methods = allowable_methods
        self.filter_fn = filter_fn
        self.disabled = False

        # Allows multiple redirects or other aliased URLs to point to the same cached response
        self.redirects = DictStorage()
        self.responses = DictStorage()

        self._include_get_headers = include_get_headers
        self._ignored_parameters = set(ignored_parameters or [])

    def is_cacheable(self, response: Union[ClientResponse, CachedResponse]) -> bool:
        """Perform all checks needed to determine if the given response should be cached"""
        return all(
            [
                not self.disabled,
                not self.is_expired(response),
                response.status in self.allowable_codes,
                response.method in self.allowable_methods,
                self.filter_fn(response),
            ]
        )

    def is_expired(self, response: AnyResponse) -> bool:
        """Determine if a given response is expired"""
        created_at = getattr(response, 'created_at', None)
        if not created_at or not self.expire_after:
            return False
        return datetime.utcnow() - created_at >= self.expire_after

    async def save_response(self, key: str, response: ClientResponse):
        """Save response to cache

        Args:
            key: Key for this response
            response: Response to save
        """
        if not self.is_cacheable(response):
            return

        response = await CachedResponse.from_client_response(response)
        await self.responses.write(key, response)

        # Alias any redirect requests to the same cache key
        for r in response.history:
            await self.redirects.write(self.create_key(r.method, r.url), key)

    async def get_response(self, key: str) -> Optional[CachedResponse]:
        """Retrieve response and timestamp for `key` if it's stored in cache,
        otherwise returns ``None```

        Args:
            key: key of resource
        """
        # Attempt to fetch response from the cache
        try:
            if key not in self.responses:
                key = await self.redirects.read(key)
            response = await self.responses.read(key)
        except (KeyError, TypeError):
            return None

        # If the item is expired or filtered out, delete it from the cache
        if not self.is_cacheable(response):
            await self.delete(key)
            response.is_expired = True

        return response

    async def clear(self):
        """Clear cache"""
        await self.responses.clear()
        await self.redirects.clear()

    async def delete(self, key: str):
        """Delete a response from the cache, along with its history (if applicable)"""

        async def delete_history(response):
            if not response:
                return
            for r in response.history:
                await self.redirects.delete(self.create_key(r.method, r.url))

        redirect_key = await self.redirects.pop(key)
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
        keys_to_delete = set()

        for key in self.responses:
            response = await self.get_response(key)
            if response and response.is_expired:
                keys_to_delete.add(key)

        logger.info(f'Deleting {len(keys_to_delete)} expired cache entries')
        for key in keys_to_delete:
            await self.delete(key)

    def has_url(self, url: str) -> bool:
        """Returns `True` if cache has `url`, `False` otherwise. Works only for GET request urls"""
        key = self.create_key('GET', url)
        return key in self.responses or key in self.redirects

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
        if self._ignored_parameters:
            url, params, body = self._remove_ignored_parameters(url, params, data)

        key = hashlib.sha256()
        key.update(method.upper().encode())
        key.update(str(url).encode())
        key.update(_encode_dict(params))
        key.update(_encode_dict(data))

        if self._include_get_headers and headers and headers != ClientRequest.DEFAULT_HEADERS:
            for name, value in sorted(headers.items()):
                key.update(name.encode())
                key.update(value.encode())
        return key.hexdigest()

    def _remove_ignored_parameters(self, url, params, data):
        def filter_ignored_params(d):
            return {k: v for k, v in d.items() if k not in self._ignored_parameters}

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
# TODO: Is there an existing ABC for async collections? Can't seem to find any.
class BaseStorage(ABCMeta):
    """A wrapper for the actual storage operations. This is separate from :py:class:`.BaseCache`
    to simplify writing to multiple tables/prefixes.

    This is no longer using a dict-like interface due to lack of python syntax support for async
    dict operations.
    """

    @abstractmethod
    async def read(self, key: str) -> Optional[ResponseOrKey]:
        """Read a single item from the cache. Returns ``None`` if the item is missing."""

    @abstractmethod
    async def read_all(self) -> Iterable[ResponseOrKey]:
        """Read all items from the cache"""

    @abstractmethod
    async def write(self, key: str, item: ResponseOrKey):
        """Write an item to the cache"""

    @abstractmethod
    async def contains(self, key: str) -> bool:
        """Check if a key is stored in the cache"""

    @abstractmethod
    async def delete(self, key: str):
        """Delete a single item from the cache. Does not raise an error if the item is missing."""

    @abstractmethod
    async def clear(self):
        """Delete all items from the cache"""

    @abstractmethod
    async def size(self) -> int:
        """Get the number of items in the cache"""

    async def pop(self, key: str) -> Optional[ResponseOrKey]:
        """Delete an item from the cache, and return the deleted item"""
        item = await self.read(key)
        await self.delete(key)
        return item


class DictStorage(UserDict, BaseStorage):
    """Simple in-memory storage that wraps a dict with the :py:class:`.BaseStorage` interface"""

    async def read(self, key: str) -> Union[CachedResponse, str]:
        return self.data[key]

    async def read_all(self) -> Iterable[ResponseOrKey]:
        return self.data.values()

    async def write(self, key: str, item: ResponseOrKey):
        self.data[key] = item

    async def delete(self, key: str):
        del self.data[key]

    async def clear(self):
        self.data.clear()

    async def size(self):
        return len(self.data)


def _encode_dict(d):
    item_pairs = [f'{k}={v}' for k, v in sorted((d or {}).items())]
    return '&'.join(item_pairs).encode()
