"""Functions for determining cache expiration based on client settings and/or cache headers"""
from datetime import datetime, timedelta
from fnmatch import fnmatch
from itertools import chain
from logging import getLogger
from typing import Any, Dict, Optional, Tuple, Union

from aiohttp import ClientResponse
from aiohttp.typedefs import StrOrURL
from multidict import CIMultiDictProxy

# Value that may be set by either Cache-Control headers or CacheBackend params to disable caching
DO_NOT_CACHE = 0

# Cache-related headers, for logging/reference; not all are supported
REQUEST_CACHE_HEADERS = [
    'Cache-Control',
    'If-Unmodified-Since',
    'If-Modified-Since',
    'If-Match',
    'If-None-Match',
]
RESPONSE_CACHE_HEADERS = ['Cache-Control', 'ETag', 'Expires', 'Age']

CacheDirective = Tuple[str, Union[None, int, bool]]
ExpirationTime = Union[None, int, float, datetime, timedelta]
ExpirationPatterns = Dict[str, ExpirationTime]
logger = getLogger(__name__)


def get_expiration(
    response: ClientResponse,
    request_expire_after: ExpirationTime = None,
    session_expire_after: ExpirationTime = None,
    urls_expire_after: ExpirationPatterns = None,
    cache_control: bool = False,
) -> ExpirationTime:
    """Get the appropriate expiration for the given response, in order of precedence:
    1. Per-request expiration
    2. Per-URL expiration
    3. Cache-Control (if enabled)
    4. Per-session expiration

    """
    return coalesce(
        request_expire_after,
        get_url_expiration(response.url, urls_expire_after),
        get_header_expiration(response.headers, cache_control),
        session_expire_after,
    )


def get_expiration_datetime(expire_after: ExpirationTime) -> Optional[datetime]:
    """Convert a relative time value or delta to an absolute datetime, if it's not already"""
    logger.debug(f'Determining expiration time based on: {expire_after}')
    if expire_after is None or expire_after == -1:
        return None
    elif isinstance(expire_after, datetime):
        return expire_after

    if not isinstance(expire_after, timedelta):
        expire_after = timedelta(seconds=expire_after)
    return datetime.utcnow() + expire_after


def get_header_expiration(headers: CIMultiDictProxy, cache_control: bool = True) -> Optional[int]:
    """Get expiration from cache headers (in seconds), if available. Currently only supports
    ``max-age`` and ``no-store``.
    """
    if not cache_control:
        return None

    # Get all Cache-Control directives, and handle multiple headers and/or comma-separated lists
    cache_directives = [v.split(',') for v in headers.getall('Cache-Control', [])]
    cache_directives = list(chain.from_iterable(cache_directives))

    kv_directives = dict([split_kv_directive(value) for value in cache_directives])
    if kv_directives.get('no-store'):
        return DO_NOT_CACHE
    return kv_directives.get('max-age')


def get_url_expiration(
    url: StrOrURL, urls_expire_after: ExpirationPatterns = None
) -> ExpirationTime:
    """Check for a matching per-URL expiration, if any"""
    for pattern, expire_after in (urls_expire_after or {}).items():
        if url_match(url, pattern):
            logger.debug(f'URL {url} matched pattern "{pattern}": {expire_after}')
            return expire_after
    return None


def coalesce(*values: Any, default=None) -> Any:
    """Get the first non-``None`` value in a list of values"""
    return next((v for v in values if v is not None), default)


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


def try_int(value: Optional[str]) -> Optional[int]:
    """Convert a string value to an int, if possible, otherwise ``None``"""
    return int(str(value)) if str(value).isnumeric() else None


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
