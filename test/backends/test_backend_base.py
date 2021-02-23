import pytest
from sys import version_info
from unittest.mock import MagicMock, patch

from aiohttp_client_cache import CachedResponse
from aiohttp_client_cache.backends.base import BaseCache, CacheBackend, DictCache  # noqa


@pytest.mark.asyncio
async def test_cache_backend__get_response__cache_response_hit():
    cache = CacheBackend()
    mock_response = MagicMock(spec=CachedResponse)
    await cache.responses.write('request-key', mock_response)

    response = await cache.get_response('request-key')
    assert response == mock_response


@pytest.mark.asyncio
async def test_cache_backend__get_response__cache_redirect_hit():
    # Set up a cache with a couple cached items and a redirect
    cache = CacheBackend()
    mock_response = MagicMock(spec=CachedResponse)
    await cache.responses.write('request-key', mock_response)
    await cache.redirects.write('redirect-key', 'request-key')

    response = await cache.get_response('redirect-key')
    assert response == mock_response


@pytest.mark.asyncio
async def test_cache_backend__get_response__cache_miss():
    cache = CacheBackend()
    await cache.responses.write('invalid-response-key', MagicMock())

    response = await cache.get_response('nonexistent-key')
    assert response is None
    response = await cache.get_response('invalid-response-key')
    assert response is None


@pytest.mark.skipif(version_info < (3, 8), reason="AsyncMock requires python 3.8+")
@pytest.mark.asyncio
@patch.object(CacheBackend, 'delete', return_value=False)
@patch.object(CacheBackend, 'is_cacheable', return_value=False)
async def test_cache_backend__get_response__cache_expired(mock_is_cacheable, mock_delete):
    cache = CacheBackend()
    await cache.responses.write('request-key', MagicMock(spec=CachedResponse))

    response = await cache.get_response('request-key')
    assert response.is_expired is True
    mock_delete.assert_called_with('request-key')


# TODO


@pytest.mark.asyncio
async def test_cache_backend__save_response():
    cache = CacheBackend()
    pass


@pytest.mark.asyncio
async def test_cache_backend__clear():
    pass


@pytest.mark.asyncio
async def test_cache_backend__delete():
    pass


@pytest.mark.asyncio
async def test_cache_backend__delete_url():
    pass


@pytest.mark.asyncio
async def test_cache_backend__delete_expired_responses():
    pass


@pytest.mark.asyncio
async def test_cache_backend__has_url():
    pass


@pytest.mark.asyncio
async def test_cache_backend__create_key():
    pass


@pytest.mark.asyncio
async def test_cache_backend__is_cacheable():
    pass


@pytest.mark.asyncio
async def test_cache_backend__is_expired():
    pass
