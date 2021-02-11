import pytest
from unittest.mock import MagicMock, patch

from aiohttp_client_cache import CachedResponse
from aiohttp_client_cache.backends import BACKEND_CLASSES, BACKEND_QUALNAMES, init_backend
from aiohttp_client_cache.backends.base import BaseCache, CacheController, DictCache  # noqa
from aiohttp_client_cache.backends.sqlite import SQLiteController


@pytest.mark.asyncio
@pytest.mark.parametrize('backend', BACKEND_QUALNAMES.keys())
@patch('gridfs.Database', MagicMock)
def test_init_backend(backend):
    cache = init_backend(backend, 'http-cache', connection=MagicMock())
    assert isinstance(cache, BACKEND_CLASSES[backend])
    assert cache.name == 'http-cache'


def test_init_backend__default():
    cache = init_backend()
    assert isinstance(cache, SQLiteController)


def test_init_backend__invalid():
    with pytest.raises(ValueError):
        init_backend('sybase')


@pytest.mark.asyncio
async def test_cache_controller__get_response__cache_hit():
    # Set up a cache with a couple cached items and a redirect
    cache = CacheController()
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
async def test_cache_controller__get_response__cache_miss():
    cache = CacheController()
    await cache.responses.write('invalid-response-key', MagicMock())

    response = await cache.get_response('nonexistent-key')
    assert response is None
    response = await cache.get_response('invalid-response-key')
    assert response is None


# TODO


@pytest.mark.asyncio
async def test_cache_controller__get_response__cache_expired():
    pass


@pytest.mark.asyncio
async def test_cache_controller__save_response():
    pass


@pytest.mark.asyncio
async def test_cache_controller__clear():
    pass


@pytest.mark.asyncio
async def test_cache_controller__delete():
    pass


@pytest.mark.asyncio
async def test_cache_controller__delete_url():
    pass


@pytest.mark.asyncio
async def test_cache_controller__delete_expired_responses():
    pass


@pytest.mark.asyncio
async def test_cache_controller__has_url():
    pass


@pytest.mark.asyncio
async def test_cache_controller__create_key():
    pass


@pytest.mark.asyncio
async def test_cache_controller__is_cacheable():
    pass


@pytest.mark.asyncio
async def test_cache_controller__is_expired():
    pass
