import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp_client_cache.backends import CacheBackend
from aiohttp_client_cache.session import CachedSession, ClientSession


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
