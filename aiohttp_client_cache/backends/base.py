from datetime import datetime, timedelta
from typing import Tuple, Optional

from dateutil.parser import parse as parse_date
from io import BytesIO
import hashlib
from urllib.parse import urlparse, parse_qsl, urlunparse

from aiohttp import ClientResponse, ClientRequest

from aiohttp_client_cache.cached_response import CachedResponse

RESPONSE_ATTRS = [
    'content',
    'cookies',
    'headers',
    'method',
    'reason',
    'request',
    'status',
    'url',
    'version',
]


class BaseCache(object):
    """Base class for cache implementations, can be used as in-memory cache.

    To extend it you can provide dictionary-like objects for
    :attr:`keys_map` and :attr:`responses` or override public methods.
    """

    def __init__(self, expire_after, include_get_headers=False, ignored_parameters=None, **kwargs):
        if expire_after is not None and not isinstance(expire_after, timedelta):
            expire_after = timedelta(seconds=expire_after)
        self._expire_after = expire_after

        self.keys_map = {}  # `key` -> `key_in_responses` mapping
        self.responses = {}  # `key_in_cache` -> `response` mapping
        self._include_get_headers = include_get_headers
        self._ignored_parameters = set(ignored_parameters or [])

    def is_expired(self, timestamp: str) -> bool:
        time_elapsed = datetime.utcnow() - parse_date(timestamp)
        return self._expire_after and time_elapsed >= self._expire_after

    def save_response(self, key: str, response: ClientResponse):
        """Save response to cache

        Args:
            key: Key for this response
            response: Response to save
        """
        self.responses[key] = self.reduce_response(response), datetime.utcnow()

    def add_key_mapping(self, new_key: str, key_to_response: str):
        """
        Adds mapping of `new_key` to `key_to_response` to make it possible to
        associate many keys with single response

        Args:
            new_key: new key (e.g. url from redirect)
            key_to_response: key which can be found in :attr:`responses`
        """
        self.keys_map[new_key] = key_to_response

    def get_response(self, key: str) -> Optional[CachedResponse]:
        """Retrieve response and timestamp for `key` if it's stored in cache,
        otherwise returns ``None```

        Args:
            key: key of resource
        """
        # Attempt to fetch response from the cache
        try:
            if key not in self.responses:
                key = self.keys_map[key]
            response, timestamp = self.responses[key]
        except (KeyError, TypeError):
            return None

        # If the item is expired, delete it from the cache
        if self.is_expired(timestamp):
            self.delete(key)
            response.is_expired = True

        return self.restore_response(response)

    def delete(self, key: str):
        """ Delete `key` from cache. Also deletes all responses from response history """
        try:
            if key in self.responses:
                response, _ = self.responses[key]
                del self.responses[key]
            else:
                response, _ = self.responses[self.keys_map[key]]
                del self.keys_map[key]
            for r in response.history:
                del self.keys_map[self.create_key(r.request)]
        # We don't care if the key is already missing from the cache
        except KeyError:
            pass

    def delete_url(self, url: str):
        """Delete response associated with `url` from cache.
        Also deletes all responses from response history. Works only for GET requests
        """
        self.delete(self.create_key('GET', url))

    def clear(self):
        """Clear cache"""
        self.responses.clear()
        self.keys_map.clear()

    def remove_expired_responses(self):
        """Deletes entries from cache with creation time older than ``expire_after``"""
        if not self._expire_after:
            return
        created_before = datetime.utcnow() - self._expire_after
        keys_to_delete = set()

        for key in self.responses:
            try:
                response, created_at = self.responses[key]
            except KeyError:
                continue
            if created_at < created_before:
                keys_to_delete.add(key)

        for key in keys_to_delete:
            self.delete(key)

    def has_key(self, key: str) -> bool:
        """Returns `True` if cache has `key`, `False` otherwise"""
        return key in self.responses or key in self.keys_map

    def has_url(self, url: str) -> bool:
        """Returns `True` if cache has `url`, `False` otherwise. Works only for GET request urls"""
        return self.has_key(self.create_key('GET', url))

    # TODO: replace these methods with CachedResponse
    def reduce_response(self, response: ClientResponse, seen=None):
        """Reduce response object to make it compatible with ``pickle``"""
        seen = seen or {}
        if id(response) in seen:
            return seen[id(response)]

        result = _Store()
        for field in RESPONSE_ATTRS:
            setattr(result, field, getattr(response, field))
        seen[id(response)] = result
        result.history = tuple(self.reduce_response(r, seen) for r in response.history)
        return result

    # def _picklable_field(self, response, name):
    #     value = getattr(response, name)
    #     if name == 'request':
    #         value = copy(value)
    #         value.hooks = []
    #     elif name == 'raw':
    #         result = _RawStore()
    #         for field in RAW_RESPONSE_ATTRS:
    #             setattr(result, field, getattr(value, field, None))
    #         value = result
    #     return value

    def restore_response(self, response, seen=None):
        """Restore response object after unpickling"""
        seen = seen or {}
        if id(response) in seen:
            return seen[id(response)]

        result = ClientResponse(response.method, response.url)
        for field in RESPONSE_ATTRS:
            setattr(result, field, getattr(response, field, None))
        result.raw._cached_content_ = result.content
        seen[id(response)] = result
        result.history = tuple(self.restore_response(r, seen) for r in response.history)
        return result

    def create_key(self, method, url, params=None, data=None, headers=None, **kwargs):
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
        return f'keys: {self.keys_map}\nresponses: {self.responses}'


# used for saving response attributes
class _Store(object):
    pass


class _RawStore(object):
    # noop for cached response
    def release_conn(self):
        pass

    # for streaming requests support
    def read(self, chunk_size=1):
        if not hasattr(self, "_io_with_content_"):
            self._io_with_content_ = BytesIO(self._cached_content_)
        return self._io_with_content_.read(chunk_size)


def _encode_dict(d):
    item_pairs = [f'{k}={v}' for k, v in sorted((d or {}).items())]
    return '&'.join(item_pairs).encode()
