import pytest
from unittest.mock import MagicMock

from aiohttp_client_cache import CachedResponse
from aiohttp_client_cache.backends.base import BaseCache, CacheBackend, DictCache  # noqa


@pytest.mark.asyncio
async def test_cache_backend__get_response__cache_hit():
    # Set up a cache with a couple cached items and a redirect
    cache = CacheBackend()
    mock_response_1 = MagicMock(spec=CachedResponse)
    mock_response_2 = MagicMock(spec=CachedResponse)
    await cache.responses.write('request-key-1', mock_response_1)
    await cache.responses.write('request-key-2', mock_response_2)
    await cache.redirects.write('redirect-key', 'request-key-2')

    response = await cache.get_response('request-key-1')
    assert response == mock_response_1
    response = await cache.get_response('redirect-key')
    assert response == mock_response_2


@pytest.mark.asyncio
async def test_cache_backend__get_response__cache_miss():
    cache = CacheBackend()
    await cache.responses.write('invalid-response-key', MagicMock())

    response = await cache.get_response('nonexistent-key')
    assert response is None
    response = await cache.get_response('invalid-response-key')
    assert response is None


# TODO


@pytest.mark.asyncio
async def test_cache_backend__get_response__cache_expired():
    pass


@pytest.mark.asyncio
async def test_cache_backend__save_response():
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
