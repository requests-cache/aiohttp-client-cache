from datetime import datetime, timedelta
from logging import getLogger
from typing import Optional, Union

from io import BytesIO
import hashlib
from urllib.parse import urlparse, parse_qsl, urlunparse

from aiohttp import ClientResponse, ClientRequest
from aiohttp_client_cache.response import CachedResponse

logger = getLogger(__name__)


class BaseCache:
    """Base class for cache implementations, can be used as in-memory cache.

    To extend it you can provide dictionary-like objects for
    :attr:`keys_map` and :attr:`responses` or override public methods.
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

        self.keys_map = {}  # `key` -> `key_in_responses` mapping
        self.responses = {}  # `key_in_cache` -> `response` mapping
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

    def is_expired(self, response: CachedResponse) -> bool:
        """Determine if a given timestamp is expired"""
        if not getattr(response, 'created_at', None) or not self.expire_after:
            return False
        return datetime.utcnow() - response.created_at >= self.expire_after

    async def save_response(self, key: str, response: ClientResponse):
        """Save response to cache

        Args:
            key: Key for this response
            response: Response to save
        """
        if not self.is_cacheable(response):
            return

        response = await CachedResponse.from_client_response(response)
        self.responses[key] = response

        # Alias any redirect requests to the same cache key
        for r in response.history:
            self.add_key_mapping(self.create_key(r.method, r.url), key)

    async def get_response(self, key: str) -> Optional[CachedResponse]:
        """Retrieve response and timestamp for `key` if it's stored in cache,
        otherwise returns ``None```

        Args:
            key: key of resource
        """
        # Attempt to fetch response from the cache
        try:
            if key not in self.responses:
                key = self.keys_map[key]
            response = self.responses[key]
        except (KeyError, TypeError):
            return None

        # If the item is expired or filtered out, delete it from the cache
        if not self.is_cacheable(response):
            self.delete(key)
            response.is_expired = True

        return response

    def add_key_mapping(self, new_key: str, key_to_response: str):
        """
        Adds mapping of `new_key` to `key_to_response` to make it possible to
        associate many keys with single response

        Args:
            new_key: new key (e.g. url from redirect)
            key_to_response: key which can be found in :attr:`responses`
        """
        self.keys_map[new_key] = key_to_response

    def clear(self):
        """Clear cache"""
        self.responses.clear()
        self.keys_map.clear()

    def delete(self, key: str):
        """ Delete `key` from cache. Also deletes all responses from response history """
        try:
            if key in self.responses:
                response = self.responses[key]
                del self.responses[key]
            else:
                response = self.responses[self.keys_map[key]]
                del self.keys_map[key]
            for r in response.history:
                del self.keys_map[self.create_key(r.method, r.url)]
        # We don't care if the key is already missing from the cache
        except KeyError:
            pass

    def delete_url(self, url: str):
        """Delete response associated with `url` from cache.
        Also deletes all responses from response history. Works only for GET requests
        """
        self.delete(self.create_key('GET', url))

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
            self.delete(key)

    def has_key(self, key: str) -> bool:
        """Returns `True` if cache has `key`, `False` otherwise"""
        return key in self.responses or key in self.keys_map

    def has_url(self, url: str) -> bool:
        """Returns `True` if cache has `url`, `False` otherwise. Works only for GET request urls"""
        return self.has_key(self.create_key('GET', url))

    def create_key(self, method, url, params=None, data=None, headers=None, **kwargs) -> str:
        """Create a unique cache key based on request details"""
        if self._ignored_parameters:
            url, params, body = self._remove_ignored_parameters(url, params, data)

        key = hashlib.sha256()
        key.update(method.upper().encode())
        key.update(url.encode())
        key.update(_encode_dict(params))
        key.update(_encode_dict(data))

        if self._include_get_headers and headers != ClientRequest.DEFAULT_HEADERS:
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

    def __str__(self):
        return f'keys: {list(self.keys_map.keys())}\nresponses: {list(self.responses.keys())}'


def _encode_dict(d):
    item_pairs = [f'{k}={v}' for k, v in sorted((d or {}).items())]
    return '&'.join(item_pairs).encode()
