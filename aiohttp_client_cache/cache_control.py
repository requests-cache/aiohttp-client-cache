"""Utilities for determining cache expiration and other cache actions"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from fnmatch import fnmatch
from functools import singledispatch
from itertools import chain
from logging import getLogger
from typing import Any, Dict, Mapping, NoReturn, Tuple, Union

from aiohttp import ClientResponse
from aiohttp.typedefs import StrOrURL
from attr import define, field
from multidict import CIMultiDict

# Value that may be set by either Cache-Control headers or CacheBackend params to disable caching
DO_NOT_CACHE = 0

# Currently supported Cache-Control directives
CACHE_DIRECTIVES = ['max-age', 'no-cache', 'no-store']

# All cache-related headers, for logging/reference; not all are supported
REQUEST_CACHE_HEADERS = [
    'Cache-Control',
    'If-Unmodified-Since',
    'If-Modified-Since',
    'If-Match',
    'If-None-Match',
]
RESPONSE_CACHE_HEADERS = ['Cache-Control', 'ETag', 'Expires', 'Age']

CacheDirective = Tuple[str, Union[None, int, bool]]
ExpirationTime = Union[None, int, float, str, datetime, timedelta]
ExpirationPatterns = Dict[str, ExpirationTime]
logger = getLogger(__name__)


@define()
class CacheActions:
    """A dataclass that contains info on specific actions to take for a given cache item.
    This is determined by a combination of CacheBackend settings and request + response headers.
    If multiple sources are provided, they will be used in the following order of precedence:

    1. Cache-Control request headers (if enabled)
    2. Cache-Control response headers (if enabled)
    3. Per-request expiration
    4. Per-URL expiration
    5. Per-session expiration
    """

    cache_control: bool = field(default=False)
    expire_after: ExpirationTime = field(default=None)
    key: str = field(default=None)
    revalidate: bool = field(default=False)  # Note: Revalidation is not currently implemented
    skip_read: bool = field(default=False)
    skip_write: bool = field(default=False)

    @classmethod
    def from_request(
        cls,
        key: str,
        cache_control: bool = False,
        cache_disabled: bool = False,
        refresh: bool = False,
        headers: Mapping | None = None,
        **kwargs,
    ):
        """Initialize from request info and CacheBackend settings"""
        if cache_disabled:
            return cls(key=key, skip_read=True, skip_write=True)
        else:
            headers = headers or {}
            if cache_control and has_cache_headers(headers):
                return cls.from_headers(key, headers)
            else:
                return cls.from_settings(
                    key, cache_control=cache_control, refresh=refresh, **kwargs
                )

    @classmethod
    def from_headers(cls, key: str, headers: Mapping):
        """Initialize from request headers"""
        directives = get_cache_directives(headers)
        do_not_cache = directives.get('max-age') == DO_NOT_CACHE
        return cls(
            cache_control=True,
            key=key,
            expire_after=directives.get('max-age'),
            skip_read=do_not_cache or 'no-store' in directives or 'no-cache' in directives,
            skip_write=do_not_cache or 'no-store' in directives,
            revalidate=False,
        )

    @classmethod
    def from_settings(
        cls,
        key: str,
        url: StrOrURL,
        cache_control: bool = False,
        refresh: bool = False,
        request_expire_after: ExpirationTime = None,
        session_expire_after: ExpirationTime = None,
        urls_expire_after: ExpirationPatterns | None = None,
        **kwargs,
    ):
        """Initialize from CacheBackend settings"""
        # Check expire_after values in order of precedence
        expire_after = coalesce(
            request_expire_after,
            get_url_expiration(url, urls_expire_after),
            session_expire_after,
        )

        do_not_cache = expire_after == DO_NOT_CACHE
        return cls(
            cache_control=cache_control,
            key=key,
            expire_after=expire_after,
            skip_read=do_not_cache,
            skip_write=do_not_cache,
            revalidate=refresh and not do_not_cache,
        )

    @property
    def expires(self) -> datetime | None:
        """Convert the user/header-provided expiration value to a datetime"""
        return get_expiration_datetime(self.expire_after)

    def update_from_response(self, response: ClientResponse):
        """Update expiration + actions based on response headers, if not previously set by request"""
        if not self.cache_control:
            return

        directives = get_cache_directives(response.headers)
        do_not_cache = directives.get('max-age') == DO_NOT_CACHE
        self.expire_after = coalesce(
            self.expires, directives.get('max-age'), directives.get('expires')
        )
        self.skip_write = self.skip_write or do_not_cache or 'no-store' in directives
        self.revalidate = self.revalidate or do_not_cache


def coalesce(*values: Any, default=None) -> Any:
    """Get the first non-``None`` value in a list of values"""
    return next((v for v in values if v is not None), default)


def get_expiration_datetime(expire_after: ExpirationTime) -> datetime | None:
    """Convert an expiration value in any supported format to an absolute datetime"""
    logger.debug(f'Determining expiration time based on: {expire_after}')
    if isinstance(expire_after, str):
        expire_after = parse_http_date(expire_after)
    if expire_after is None or expire_after == -1:
        return None
    if isinstance(expire_after, datetime):
        return convert_to_utc_naive(expire_after)

    if not isinstance(expire_after, timedelta):
        assert isinstance(expire_after, (int, float))
        expire_after = timedelta(seconds=expire_after)
    return utcnow() + expire_after


def get_cache_directives(headers: Mapping) -> dict:
    """Get all Cache-Control directives, and handle multiple headers and comma-separated lists"""
    if not headers:
        return {}
    if not hasattr(headers, 'getall'):
        headers = CIMultiDict(headers)

    header_values = headers.getall('Cache-Control', [])  # type: ignore
    cache_directives = [v.split(',') for v in header_values if v]
    cache_directives = list(chain.from_iterable(cache_directives))
    kv_directives = dict([split_kv_directive(value) for value in cache_directives])

    if 'Expires' in headers:
        kv_directives['expires'] = headers.getone('Expires')  # type: ignore
    return kv_directives


def get_url_expiration(
    url: StrOrURL, urls_expire_after: ExpirationPatterns | None = None
) -> ExpirationTime:
    """Check for a matching per-URL expiration, if any"""
    for pattern, expire_after in (urls_expire_after or {}).items():
        if url_match(url, pattern):
            logger.debug(f'URL {url} matched pattern "{pattern}": {expire_after}')
            return expire_after
    return None


def has_cache_headers(headers: Mapping) -> bool:
    """Determine if headers contain cache directives **that we currently support**"""
    ci_headers = CIMultiDict(headers)
    cache_control = ','.join(ci_headers.getall('Cache-Control', []))
    return any([d in cache_control for d in CACHE_DIRECTIVES] + [bool(headers.get('Expires'))])


def compose_refresh_headers(
    request_headers: Mapping | None, cached_headers: Mapping
) -> tuple[bool, Mapping]:
    """Returns headers containing directives for conditional requests if the cached headers support it"""
    refresh_headers = dict(request_headers) if request_headers is not None else {}
    conditional_request_supported = False

    if 'ETag' in cached_headers:
        refresh_headers['If-None-Match'] = cached_headers['ETag']
        conditional_request_supported = True

    if 'Last-Modified' in cached_headers:
        refresh_headers['If-Modified-Since'] = cached_headers['Last-Modified']
        conditional_request_supported = True

    return conditional_request_supported, refresh_headers


if sys.version_info >= (3, 10):

    def parse_http_date(value: str) -> datetime | None:
        """Attempt to parse an HTTP (RFC 5322-compatible) timestamp"""
        try:
            return parsedate_to_datetime(value)
        except ValueError:
            logger.debug(f'Failed to parse timestamp: {value}')
            return None

else:  # pragma: no cover

    def parse_http_date(value: str) -> datetime | None:
        """Attempt to parse an HTTP (RFC 5322-compatible) timestamp"""
        try:
            return parsedate_to_datetime(value)
        except (ValueError, TypeError):
            logger.debug(f'Failed to parse timestamp: {value}')
            return None


def split_kv_directive(header_value: str) -> CacheDirective:
    """Split a cache directive into a ``(header_value, int)`` key-value pair, if possible;
    otherwise just ``(header_value, True)``.
    """
    header_value = header_value.strip()
    if '=' in header_value:
        k, v = header_value.split('=', 1)
        return k, try_int(v)
    else:
        return header_value, True


def convert_to_utc_naive(dt: datetime):
    """All internal datetimes are UTC and timezone-naive. Convert any user/header-provided
    datetimes to the same format.
    """
    if dt.tzinfo:
        dt.astimezone(timezone.utc)
        dt = dt.replace(tzinfo=None)
    return dt


# TODO: This could be replaced with timezone-aware datetimes, but this will cause problems with
# existing cache data. It would be best to do this at the same time as a release that includes
# changes to request matching logic (i.e., new cache keys).
def utcnow() -> datetime:
    """Get the current time in UTC, as a timezone-naive datetime"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


@singledispatch
def try_int(value):
    raise NotImplementedError


@try_int.register
def _(value: None) -> None:
    return value


@try_int.register
def _(value: int) -> int:
    return value


@try_int.register
def _(value: float) -> NoReturn:
    # Make sure that we do not inadvertently process a supertype of `int`.
    raise TypeError


@try_int.register
def _(value: bool) -> NoReturn:
    # Make sure that we do not inadvertently process a supertype of `int`.
    raise TypeError


@try_int.register
def _(value: str):
    try:
        return int(value)
    except ValueError:
        return None


def url_match(url: StrOrURL, pattern: str) -> bool:
    """Determine if a URL matches a pattern

    Args:
        url: URL to test. Its base URL (without protocol) will be used.
        pattern: Glob pattern to match against. A recursive wildcard will be added if not present

    Example:
        >>> url_match('https://httpbin.org/delay/1', 'httpbin.org/delay')
        True
        >>> url_match('https://httpbin.org/stream/1', 'httpbin.org/*/1')
        True
        >>> url_match('https://httpbin.org/stream/2', 'httpbin.org/*/1')
        False
    """
    if not url:
        return False
    url = str(url).split('://')[-1]
    pattern = pattern.split('://')[-1].rstrip('*') + '**'
    return fnmatch(url, pattern)
