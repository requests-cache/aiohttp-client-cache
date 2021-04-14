import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from multidict import CIMultiDict, CIMultiDictProxy

from aiohttp_client_cache.cache_control import DO_NOT_CACHE, get_expiration, get_expiration_datetime

IGNORED_DIRECTIVES = [
    'must-revalidate',
    'no-cache',
    'no-transform',
    'private',
    'proxy-revalidate',
    'public',
    's-maxage=<seconds>',
]


@pytest.mark.parametrize(
    'url, request_expire_after, expected_expiration',
    [
        ('img.site_1.com', None, timedelta(hours=12)),
        ('img.site_1.com', 60, 60),
        ('http://img.site.com/base/', None, 1),
        ('https://img.site.com/base/img.jpg', None, 1),
        ('site_2.com/resource_1', None, timedelta(hours=20)),
        ('http://site_2.com/resource_1/index.html', None, timedelta(hours=20)),
        ('http://site_2.com/resource_2/', None, timedelta(days=7)),
        ('http://site_2.com/static/', None, -1),
        ('http://site_2.com/static/img.jpg', None, -1),
        ('site_2.com', None, 1),
        ('site_2.com', 60, 60),
        ('some_other_site.com', None, 1),
        ('some_other_site.com', 60, 60),
    ],
)
def test_get_expiration(url, request_expire_after, expected_expiration):
    """Test get_expiration with per-session, per-request, and per-URL expiration"""
    session_expire_after = 1
    urls_expire_after = {
        '*.site_1.com': timedelta(hours=12),
        'site_2.com/resource_1': timedelta(hours=20),
        'site_2.com/resource_2': timedelta(days=7),
        'site_2.com/static': -1,
    }
    expiration = get_expiration(
        MagicMock(url=url), request_expire_after, session_expire_after, urls_expire_after
    )
    assert expiration == expected_expiration


@pytest.mark.parametrize(
    'headers, expected_expiration',
    [
        ([], 1),
        ([('Cache-Control', 'max-age=60')], 60),
        ([('Cache-Control', 'public, max-age=60')], 60),
        ([('Cache-Control', 'public'), ('Cache-Control', 'max-age=60')], 60),
        ([('Cache-Control', 'max-age=0')], DO_NOT_CACHE),
        ([('Cache-Control', 'no-store')], DO_NOT_CACHE),
    ],
)
def test_get_expiration__cache_control(headers, expected_expiration):
    """Test get_expiration with Cache-Control response headers"""
    url = 'https://img.site.com/base/img.jpg'
    response = MagicMock(url=url, headers=CIMultiDictProxy(CIMultiDict(headers)))
    expiration = get_expiration(response, session_expire_after=1, cache_control=True)
    assert expiration == expected_expiration


@pytest.mark.parametrize(
    'request_expire_after, url_expire_after, header_expire_after, expected_expiration',
    [
        (None, None, None, 1),
        (2, None, None, 2),
        (2, 3, None, 2),
        (2, None, 4, 2),
        (2, 3, 4, 2),
        (None, 3, None, 3),
        (None, 3, 4, 3),
        (None, None, 4, 4),
    ],
)
@patch('aiohttp_client_cache.cache_control.get_header_expiration')
@patch('aiohttp_client_cache.cache_control.get_url_expiration')
def test_get_expiration__precedence(
    get_url_expiration,
    get_header_expiration,
    request_expire_after,
    url_expire_after,
    header_expire_after,
    expected_expiration,
):
    """Test get_expiration precedence with various combinations or per-request, per-session,
    per-URL, and Cache-Control expiration
    """
    url = 'https://img.site.com/base/img.jpg'
    get_url_expiration.return_value = url_expire_after
    get_header_expiration.return_value = header_expire_after

    expiration = get_expiration(
        MagicMock(url=url), request_expire_after, session_expire_after=1, cache_control=True
    )
    assert expiration == expected_expiration


@pytest.mark.parametrize('directive', IGNORED_DIRECTIVES)
def test_get_expiration__ignored_headers(directive):
    """Ensure that currently unimplemented Cache-Control headers do not affect behavior"""
    url = 'https://img.site.com/base/img.jpg'
    headers = CIMultiDictProxy(CIMultiDict([('Cache-Control', directive)]))
    response = MagicMock(url=url, headers=headers)
    expiration = get_expiration(response, session_expire_after=1, cache_control=True)
    assert expiration == 1


def test_get_expiration_datetime__no_expiration():
    assert get_expiration_datetime(None) is None
    assert get_expiration_datetime(-1) is None


@pytest.mark.parametrize(
    'expire_after, expected_expiration_delta',
    [
        (datetime.utcnow(), timedelta(seconds=0)),
        (timedelta(seconds=60), timedelta(seconds=60)),
        (60, timedelta(seconds=60)),
        (33.3, timedelta(seconds=33.3)),
    ],
)
def test_get_expiration_datetime__relative(expire_after, expected_expiration_delta):
    expires = get_expiration_datetime(expire_after)
    expected_expiration = datetime.utcnow() + expected_expiration_delta
    # Instead of mocking datetime (which adds some complications), check for approximate value
    assert abs((expires - expected_expiration).total_seconds()) <= 5
