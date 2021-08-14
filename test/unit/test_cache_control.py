from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from multidict import CIMultiDict, CIMultiDictProxy
from yarl import URL

from aiohttp_client_cache.cache_control import DO_NOT_CACHE, CacheActions, get_expiration_datetime
from test.conftest import HTTPDATE_DATETIME, HTTPDATE_STR

IGNORED_DIRECTIVES = [
    'must-revalidate',
    'no-transform',
    'private',
    'proxy-revalidate',
    'public',
    's-maxage=<seconds>',
]


@pytest.mark.parametrize(
    'request_expire_after, url_expire_after, header_expire_after, expected_expiration',
    [
        (None, None, None, 1),
        (2, None, None, 2),
        (2, 3, None, 2),
        (None, 3, None, 3),
        (2, 3, 4, 4),
        (2, None, 4, 4),
        (None, 3, 4, 4),
        (None, None, 4, 4),
    ],
)
@patch('aiohttp_client_cache.cache_control.get_url_expiration')
def test_init_from_request(
    get_url_expiration,
    request_expire_after,
    url_expire_after,
    header_expire_after,
    expected_expiration,
):
    """Test precedence with various combinations or per-request, per-session, per-URL, and
    Cache-Control expiration
    """
    url = 'https://img.site.com/base/img.jpg'
    get_url_expiration.return_value = url_expire_after
    headers = {'Cache-Control': f'max-age={header_expire_after}'} if header_expire_after else {}

    actions = CacheActions.from_request(
        key='key',
        url=URL(url),
        request_expire_after=request_expire_after,
        session_expire_after=1,
        cache_control=True,
        headers=headers,
    )
    assert actions.expire_after == expected_expiration


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
def test_init_from_settings(url, request_expire_after, expected_expiration):
    """Test with per-session, per-request, and per-URL expiration"""
    urls_expire_after = {
        '*.site_1.com': timedelta(hours=12),
        'site_2.com/resource_1': timedelta(hours=20),
        'site_2.com/resource_2': timedelta(days=7),
        'site_2.com/static': -1,
    }
    actions = CacheActions.from_settings(
        key='key',
        url=URL(url),
        request_expire_after=request_expire_after,
        session_expire_after=1,
        urls_expire_after=urls_expire_after,
    )
    assert actions.expire_after == expected_expiration


@pytest.mark.parametrize(
    'headers, expected_expiration',
    [
        ([], None),
        ([('Expires', HTTPDATE_STR)], None),  # Only valid for response headers
        ([('Cache-Control', 'max-age=60')], 60),
        ([('Cache-Control', 'public, max-age=60')], 60),
        ([('Cache-Control', 'public'), ('Cache-Control', 'max-age=60')], 60),
        ([('Cache-Control', 'max-age=0')], DO_NOT_CACHE),
        ([('Cache-Control', 'no-store')], DO_NOT_CACHE),
    ],
)
def test_init_from_headers(headers, expected_expiration):
    """Test with Cache-Control request headers"""
    actions = CacheActions.from_headers(key='key', headers=CIMultiDict(headers))

    assert actions.key == 'key'
    if expected_expiration == DO_NOT_CACHE:
        assert actions.skip_read is True
        assert actions.skip_write is True
    else:
        assert actions.expire_after == expected_expiration
        assert actions.skip_read is False
        assert actions.skip_write is False


@pytest.mark.parametrize(
    'headers, expected_expiration',
    [
        ([], None),
        ([('Cache-Control', 'no-cache')], None),  # Only valid for request headers
        ([('Cache-Control', 'max-age=60')], 60),
        ([('Cache-Control', 'public, max-age=60')], 60),
        ([('Cache-Control', 'public'), ('Cache-Control', 'max-age=60')], 60),
        ([('Cache-Control', 'max-age=0')], DO_NOT_CACHE),
        ([('Cache-Control', 'no-store')], DO_NOT_CACHE),
        ([('Expires', HTTPDATE_STR)], HTTPDATE_STR),
        ([('Expires', HTTPDATE_STR), ('Cache-Control', 'max-age=60')], 60),
    ],
)
def test_update_from_response(headers, expected_expiration):
    """Test with Cache-Control response headers"""
    url = 'https://img.site.com/base/img.jpg'
    response = MagicMock(url=url, headers=CIMultiDictProxy(CIMultiDict(headers)))
    actions = CacheActions(key='key', cache_control=True)
    actions.update_from_response(response)

    if expected_expiration == DO_NOT_CACHE:
        assert actions.skip_write is True
    else:
        assert actions.expire_after == expected_expiration
        assert actions.skip_write is False


def test_update_from_response__disabled():
    """Response headers should not be used if cache_control=False"""
    url = 'https://img.site.com/base/img.jpg'
    headers = [('Cache-Control', 'max-age=60')]
    response = MagicMock(url=url, headers=CIMultiDictProxy(CIMultiDict(headers)))

    actions = CacheActions(key='key', cache_control=False, expire_after=30)
    actions.update_from_response(response)
    assert actions.expire_after == 30


@pytest.mark.parametrize('directive', IGNORED_DIRECTIVES)
def test_ignored_headers(directive):
    """Ensure that currently unimplemented Cache-Control headers do not affect behavior"""
    url = 'https://img.site.com/base/img.jpg'
    headers = {'Cache-Control': directive}
    # expiration = get_expiration(response, session_expire_after=1, cache_control=True)
    actions = CacheActions.from_request(
        key='key',
        url=URL(url),
        session_expire_after=1,
        cache_control=True,
        headers=headers,
    )
    assert actions.expire_after == 1


def test_get_expiration_datetime__no_expiration():
    assert get_expiration_datetime(None) is None
    assert get_expiration_datetime(-1) is None


@pytest.mark.parametrize(
    'expire_after, expected_expiration_delta',
    [
        (None, timedelta(seconds=0)),
        (timedelta(seconds=60), timedelta(seconds=60)),
        (60, timedelta(seconds=60)),
        (33.3, timedelta(seconds=33.3)),
    ],
)
def test_get_expiration_datetime__relative(expire_after, expected_expiration_delta):
    expires = get_expiration_datetime(expire_after or datetime.utcnow())
    expected_expiration = datetime.utcnow() + expected_expiration_delta
    # Instead of mocking datetime (which adds some complications), check for approximate value
    assert abs((expires - expected_expiration).total_seconds()) < 1


def test_get_expiration_datetime__httpdate():
    assert get_expiration_datetime(HTTPDATE_STR) == HTTPDATE_DATETIME
    assert get_expiration_datetime('P12Y34M56DT78H90M12.345S') is None
