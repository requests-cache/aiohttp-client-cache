"""Functions for determining cache expiration"""
from datetime import datetime, timedelta
from fnmatch import fnmatch
from logging import getLogger
from typing import Dict, Optional, Union

from aiohttp import ClientResponse
from aiohttp.typedefs import StrOrURL

ExpirationTime = Union[None, int, float, datetime, timedelta]
ExpirationPatterns = Dict[str, ExpirationTime]
logger = getLogger(__name__)


def get_expiration(
    response: ClientResponse,
    request_expire_after: ExpirationTime = None,
    session_expire_after: ExpirationTime = None,
    urls_expire_after: ExpirationPatterns = None,
) -> Optional[datetime]:
    """Get the appropriate expiration for the given response, in order of precedence:
    1. Per-request expiration
    2. Per-URL expiration
    3. Per-session expiration

    Returns:
        An absolute expiration :py:class:`.datetime` or ``None``
    """
    return get_expiration_datetime(
        request_expire_after
        or get_expiration_for_url(response.url, urls_expire_after)
        or session_expire_after
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


def get_expiration_for_url(
    url: StrOrURL, urls_expire_after: ExpirationPatterns = None
) -> ExpirationTime:
    """Check for a matching per-URL expiration, if any"""
    for pattern, expire_after in (urls_expire_after or {}).items():
        if url_match(url, pattern):
            logger.debug(f'URL {url} matched pattern "{pattern}": {expire_after}')
            return expire_after
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
