from unittest.mock import MagicMock, patch

import pytest

from aiohttp_client_cache.backends import CacheBackend
from aiohttp_client_cache.cache_control import CacheActions
from aiohttp_client_cache.session import CachedSession, ClientSession

pytestmark = [pytest.mark.asyncio]

# AsyncMock was added to the stdlib in python 3.8
try:
    from unittest.mock import AsyncMock
except ImportError:
    pytestmark += [pytest.mark.skip(reason='Tests require AsyncMock from python 3.8+')]


@patch.object(ClientSession, '_request')
async def test_session__cache_hit(mock_request):
    cache = MagicMock(spec=CacheBackend)
    cache.request.return_value = AsyncMock(is_expired=False), CacheActions()
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
async def test_session__default_attrs(mock_request):
    cache = MagicMock(spec=CacheBackend)
    cache.request.return_value = None, CacheActions()
    session = CachedSession(cache=cache)

    response = await session.get('http://test.url')
    assert response.from_cache is False and response.is_expired is False
