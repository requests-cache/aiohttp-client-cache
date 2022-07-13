from http.cookies import SimpleCookie
from unittest.mock import MagicMock, patch

import pytest
from yarl import URL

from aiohttp_client_cache.backends import CacheBackend
from aiohttp_client_cache.cache_control import CacheActions
from aiohttp_client_cache.session import CachedSession, ClientSession

pytestmark = [pytest.mark.asyncio]

# AsyncMock was added to the stdlib in python 3.8
try:
    from unittest.mock import AsyncMock
except ImportError:
    pytestmark += [pytest.mark.skip(reason='Tests require AsyncMock from python 3.8+')]


async def test_session__init_kwargs():
    cookie_jar = MagicMock()
    base_url = 'https://test.com'
    session = CachedSession(
        cache=MagicMock(spec=CacheBackend),
        base_url=base_url,
        cookie_jar=cookie_jar,
    )

    assert session._base_url == URL(base_url)
    assert session._cookie_jar is cookie_jar


async def test_session__init_posarg():
    base_url = 'https://test.com'
    session = CachedSession(base_url, cache=MagicMock(spec=CacheBackend))
    assert session._base_url == URL(base_url)


@patch.object(ClientSession, '_request')
async def test_session__cache_hit(mock_request):
    cache = MagicMock(spec=CacheBackend)
    response = AsyncMock(is_expired=False, url=URL('https://test.com'))
    cache.request.return_value = response, CacheActions()
    session = CachedSession(cache=cache)

    await session.get('http://test.url')
    assert mock_request.called is False


@patch.object(ClientSession, '_request')
async def test_session__cache_expired_or_invalid(mock_request):
    cache = MagicMock(spec=CacheBackend)
    cache.request.return_value = None, CacheActions()
    session = CachedSession(cache=cache)

    await session.get('http://test.url')
    assert mock_request.called is True


@patch.object(ClientSession, '_request')
async def test_session__cache_miss(mock_request):
    cache = MagicMock(spec=CacheBackend)
    cache.request.return_value = None, CacheActions()
    session = CachedSession(cache=cache)

    await session.get('http://test.url')
    assert mock_request.called is True


@patch.object(ClientSession, '_request')
async def test_session__request_expire_after(mock_request):
    cache = MagicMock(spec=CacheBackend)
    cache.request.return_value = None, CacheActions()
    session = CachedSession(cache=cache)

    await session.get('http://test.url', expire_after=10)
    assert mock_request.called is True
    assert 'expire_after' not in mock_request.call_args


@patch.object(ClientSession, '_request')
async def test_session__default_attrs(mock_request):
    cache = MagicMock(spec=CacheBackend)
    cache.request.return_value = None, CacheActions()
    session = CachedSession(cache=cache)

    response = await session.get('http://test.url')
    assert response.from_cache is False and response.is_expired is False


@pytest.mark.parametrize(
    "params",
    [
        {'param': 'value'},  # Dict of strings
        {'param': 4.2},  # Dict of floats
        (('param', 'value'),),  # Tuple of (key, value) pairs
        'param',  # string
    ],
)
@patch.object(ClientSession, '_request')
async def test_all_param_types(mock_request, params) -> None:
    """Ensure that CachedSession.request() acceepts all the same parameter types as aiohttp"""
    cache = MagicMock(spec=CacheBackend)
    cache.request.return_value = None, CacheActions()
    session = CachedSession(cache=cache)

    response = await session.get('http://test.url', params=params)
    assert response.from_cache is False


@patch.object(ClientSession, '_request')
async def test_session__cookies(mock_request):
    cache = MagicMock(spec=CacheBackend)
    response = AsyncMock(
        is_expired=False,
        url=URL('https://test.com'),
        cookies=SimpleCookie({'test_cookie': 'value'}),
    )
    cache.request.return_value = response, CacheActions()
    session = CachedSession(cache=cache)

    session.cookie_jar.clear()
    await session.get('http://test.url')
    cookies = session.cookie_jar.filter_cookies('https://test.com')
    assert cookies['test_cookie'].value == 'value'


@patch.object(ClientSession, '_request')
async def test_session__empty_cookies(mock_request):
    """Previous versions didn't set cookies if they were empty. Just make sure it doesn't explode."""
    cache = MagicMock(spec=CacheBackend)
    response = AsyncMock(is_expired=False, url=URL('https://test.com'), cookies=None)
    cache.request.return_value = response, CacheActions()
    session = CachedSession(cache=cache)

    session.cookie_jar.clear()
    await session.get('http://test.url')
    assert not session.cookie_jar.filter_cookies('https://test.com')
