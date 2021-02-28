import pytest
from sys import version_info
from unittest.mock import MagicMock, patch

from aiohttp_client_cache.backends import CacheBackend
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
    cache.get_response.return_value = AsyncMock(is_expired=False)
    session = CachedSession(cache=cache)

    await session.get('http://test.url')
    assert mock_request.called is False


@patch.object(ClientSession, '_request')
async def test_session__cache_expired_or_invalid(mock_request):
    cache = MagicMock(spec=CacheBackend)
    cache.get_response.return_value = None
    session = CachedSession(cache=cache)

    await session.get('http://test.url')
    assert mock_request.called is True


@patch.object(ClientSession, '_request')
async def test_session__cache_miss(mock_request):
    cache = MagicMock(spec=CacheBackend)
    cache.get_response.return_value = None
    session = CachedSession(cache=cache)

    await session.get('http://test.url')
    assert mock_request.called is True
