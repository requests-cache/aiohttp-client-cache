import pytest
import sys
from unittest.mock import MagicMock, patch

from aiohttp_client_cache.backends import CacheBackend
from aiohttp_client_cache.session import CachedSession, ClientSession

# AsyncMock was added in python 3.8
try:
    from unittest.mock import AsyncMock
except ImportError:
    pass
pytestmark = pytest.mark.skipif(sys.version_info < (3, 8), reason="requires python 3.8 or higher")


@pytest.mark.asyncio
@patch.object(ClientSession, '_request')
async def test_session__cache_hit(mock_request):
    cache = MagicMock(spec=CacheBackend)
    cache.get_response.return_value = AsyncMock(is_expired=False)
    session = CachedSession(cache=cache)

    await session.get('http://test.url')
    assert mock_request.called is False


@pytest.mark.asyncio
@patch.object(ClientSession, '_request')
async def test_session__cache_expired(mock_request):
    cache = MagicMock(spec=CacheBackend)
    cache.get_response.return_value = AsyncMock(is_expired=True)
    session = CachedSession(cache=cache)

    await session.get('http://test.url')
    assert mock_request.called is True


@pytest.mark.asyncio
@patch.object(ClientSession, '_request')
async def test_session__cache_miss(mock_request):
    cache = MagicMock(spec=CacheBackend)
    cache.get_response.return_value = None
    session = CachedSession(cache=cache)

    await session.get('http://test.url')
    assert mock_request.called is True
