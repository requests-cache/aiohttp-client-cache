import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from aiohttp_client_cache.expiration import get_expiration, get_expiration_datetime


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
@patch('aiohttp_client_cache.expiration.get_expiration_datetime', side_effect=lambda x: x)
def test_get_expiration(
    mock_get_expiration_datetime, url, request_expire_after, expected_expiration
):
    """Test expiration precedence and URL patterns for get_expiration.
    Mocking out datetime conversion to test in a separate test function.
    """
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
