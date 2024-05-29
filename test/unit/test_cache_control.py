from __future__ import annotations

import os
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from test.conftest import HTTPDATE_DATETIME, HTTPDATE_STR
from typing import Any, Mapping
from unittest.mock import MagicMock, patch

import pytest
from faker import Faker
from multidict import CIMultiDict, CIMultiDictProxy
from yarl import URL

from aiohttp_client_cache.cache_control import (
    DO_NOT_CACHE,
    CacheActions,
    compose_refresh_headers,
    convert_to_utc_naive,
    get_expiration_datetime,
    parse_http_date,
    split_kv_directive,
    try_int,
    url_match,
    utcnow,
)

# Any random value, but to support `pytest-xdist` the value must be static during a Pytest session.
DEFAULT_FAKER_SEED = os.getenv('CUSTOM_FAKER_SEED') or 42

Faker.seed(os.getenv('GITHUB_JOB') or DEFAULT_FAKER_SEED)
fake = Faker()
# Make sure "pytest-xdist" collects the same datetime object.
RANDOM_DATETIME_NOW_UTC = fake.date_time(tzinfo=timezone.utc).replace(second=0)

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
        urls_expire_after=urls_expire_after,  # type: ignore[arg-type]
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
    expires = get_expiration_datetime(expire_after or utcnow())
    expected_expiration = utcnow() + expected_expiration_delta
    # Instead of mocking datetime (which adds some complications), check for approximate value
    assert abs((expires - expected_expiration).total_seconds()) < 1


def test_get_expiration_datetime__httpdate():
    assert get_expiration_datetime(HTTPDATE_STR) == HTTPDATE_DATETIME
    assert get_expiration_datetime('P12Y34M56DT78H90M12.345S') is None


@pytest.mark.parametrize(
    'request_headers, cached_headers, conditional_request_supported, expected_refresh_headers',
    [
        (
            None,
            {
                'Last-Modified': 'Tue, 16 Jan 2024 13:05:41 GMT',
                'ETag': 'ecf4cd5e9ff144a589d45ca6b2f623f4',
            },
            True,
            {
                'If-Modified-Since': 'Tue, 16 Jan 2024 13:05:41 GMT',
                'If-None-Match': 'ecf4cd5e9ff144a589d45ca6b2f623f4',
            },
        ),
        (
            None,
            {'Last-Modified': 'Tue, 16 Jan 2024 13:05:41 GMT'},
            True,
            {
                'If-Modified-Since': 'Tue, 16 Jan 2024 13:05:41 GMT',
            },
        ),
        (
            None,
            {'ETag': 'ecf4cd5e9ff144a589d45ca6b2f623f4'},
            True,
            {
                'If-None-Match': 'ecf4cd5e9ff144a589d45ca6b2f623f4',
            },
        ),
        (None, {'foo': 'bar'}, False, {}),
        ({'foo': 'bar'}, {'ETag': 123}, True, {'foo': 'bar', 'If-None-Match': 123}),
        ({'foo': 'bar'}, {}, False, {'foo': 'bar'}),
    ],
)
def test_compose_refresh_headers(
    request_headers: Mapping | None,
    cached_headers: Mapping,
    conditional_request_supported: bool,
    expected_refresh_headers: Mapping,
) -> None:
    refresh_headers = compose_refresh_headers(request_headers, cached_headers)
    assert refresh_headers[0] == conditional_request_supported
    assert refresh_headers[1] == expected_refresh_headers


@pytest.mark.parametrize(
    'value, expected_output',
    [
        (
            format_datetime(RANDOM_DATETIME_NOW_UTC, usegmt=False),
            RANDOM_DATETIME_NOW_UTC.replace(microsecond=0),
        ),
        (
            format_datetime(RANDOM_DATETIME_NOW_UTC, usegmt=True),
            RANDOM_DATETIME_NOW_UTC.replace(microsecond=0),
        ),
        (fake.pystr(), None),
    ],
)
def test_parse_http_date(value: Any, expected_output: datetime | None) -> None:
    assert parse_http_date(value) == expected_output


@pytest.mark.parametrize(
    'value, expected_output',
    [
        ('public', ('public', True)),
        (' max-age=60', ('max-age', 60)),
        ('foo=bar', ('foo', None)),
        ('no-store', ('no-store', True)),
        ('=', ('', None)),
        ('', ('', True)),
    ],
)
def test_split_kv_directive(value, expected_output) -> None:
    assert split_kv_directive(value) == expected_output


@pytest.mark.parametrize(
    'dt, dt_utc',
    [
        (RANDOM_DATETIME_NOW_UTC, RANDOM_DATETIME_NOW_UTC.replace(tzinfo=None)),
        (
            RANDOM_DATETIME_NOW_UTC.replace(tzinfo=None),
            RANDOM_DATETIME_NOW_UTC.replace(tzinfo=None),
        ),
    ],
)
def test_convert_to_utc_naive(dt: datetime, dt_utc: datetime) -> None:
    assert convert_to_utc_naive(dt) == pytest.approx(dt_utc)


@pytest.mark.parametrize(
    'url, pattern, expected_output',
    [
        ('', ..., False),
        ('https://httpbin.org/delay/1', 'httpbin.org/delay', True),
        ('https://httpbin.org/delay/1', 'httpbin.org/delay', True),
        ('https://httpbin.org/stream/1', 'httpbin.org/*/1', True),
        ('httpbin.org/stream/1', 'httpbin.org/*/1', True),
        ('https://httpbin.org/stream/1', '*', True),
        ('https://httpbin.org/stream/1', '', True),
        (fake.pystr(), '*', True),
        (URL('https://httpbin.org/stream/2'), 'httpbin.org/*/1', False),
        (URL('https://httpbin.org/stream/1'), 'httpbin.org/*/1', True),
        (URL('https://httpbin.org/stream/2'), 'httpbin.org/*/1', False),
    ],
)
def test_url_match(url: Any, pattern: str, expected_output: bool) -> None:
    assert url_match(url, pattern) == expected_output


@pytest.mark.parametrize(
    'value, expected_output, error',
    [
        (
            str(random_int := fake.pyint()),
            random_int,
            None,
        ),  # `str` (numeric) to `int`.
        ('0', 0, None),  # `str` (numeric) to `int`.
        (None, None, None),  # `None` to `None`.
        (random_int, random_int, None),  # `int` to `int`.
        (fake.pystr(), None, None),  # `str` (non-numeric) to `None`.
        (fake.pybool(), ..., TypeError),  # Unsupported type.
        (fake.pyfloat(), ..., TypeError),  # Unsupported type.
        (fake.pyiterable(), ..., NotImplementedError),  # Unsupported type.
    ],
)
def test_try_int(value: Any, expected_output: str | None, error: type[Exception] | None) -> None:
    ctx = pytest.raises(error) if error else nullcontext()
    with ctx:
        assert try_int(value) == expected_output
