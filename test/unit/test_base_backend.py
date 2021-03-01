import pytest
from sys import version_info
from unittest.mock import MagicMock, patch

from aiohttp_client_cache import CachedResponse
from aiohttp_client_cache.backends import (
    BaseCache,
    CacheBackend,
    DictCache,
    get_placeholder_backend,
)

pytestmark = pytest.mark.asyncio


def test_get_placeholder_backend():
    class TestBackend:
        def __init__(self):
            import nonexistent_module

    try:
        TestBackend()
    except ImportError as e:
        placeholder = get_placeholder_backend(e)

    # Initializing the placeholder class should re-raise the original ImportError
    with pytest.raises(ImportError):
        placeholder()


async def test_get_response__cache_response_hit():
    cache = CacheBackend()
    mock_response = MagicMock(spec=CachedResponse, method='GET', status=200, is_expired=False)
    await cache.responses.write('request-key', mock_response)

    response = await cache.get_response('request-key')
    assert response == mock_response


async def test_get_response__cache_redirect_hit():
    # Set up a cache with a couple cached items and a redirect
    cache = CacheBackend()
    mock_response = MagicMock(spec=CachedResponse, method='GET', status=200, is_expired=False)
    await cache.responses.write('request-key', mock_response)
    await cache.redirects.write('redirect-key', 'request-key')

    response = await cache.get_response('redirect-key')
    assert response == mock_response


async def test_get_response__cache_miss():
    cache = CacheBackend()
    await cache.responses.write('invalid-response-key', MagicMock())

    response = await cache.get_response('nonexistent-key')
    assert response is None
    response = await cache.get_response('invalid-response-key')
    assert response is None


@pytest.mark.skipif(version_info < (3, 8), reason='Tests require AsyncMock from python 3.8+')
@patch.object(CacheBackend, 'delete', return_value=False)
@patch.object(CacheBackend, 'is_cacheable', return_value=False)
async def test_get_response__cache_expired(mock_is_cacheable, mock_delete):
    cache = CacheBackend()
    mock_response = MagicMock(spec=CachedResponse, method='GET', status=200, is_expired=True)
    await cache.responses.write('request-key', mock_response)

    response = await cache.get_response('request-key')
    assert response is None
    mock_delete.assert_called_with('request-key')


@pytest.mark.skipif(version_info < (3, 8), reason='Tests require AsyncMock from python 3.8+')
@patch.object(CacheBackend, 'is_cacheable', return_value=True)
async def test_save_response(mock_is_cacheable):
    cache = CacheBackend()
    mock_response = MagicMock()
    mock_response.history = [MagicMock(method='GET', url='test')]
    redirect_key = cache.create_key('GET', 'test')

    await cache.save_response('key', mock_response)
    cached_response = await cache.responses.read('key')
    assert cached_response and isinstance(cached_response, CachedResponse)
    assert await cache.redirects.read(redirect_key) == 'key'


@patch.object(CacheBackend, 'is_cacheable', return_value=False)
async def test_save_response__not_cacheable(mock_is_cacheable):
    cache = CacheBackend()
    await cache.save_response('key', MagicMock())
    assert 'key' not in cache.responses


async def test_clear():
    cache = CacheBackend()
    await cache.responses.write('key', 'value')
    await cache.redirects.write('key', 'value')
    await cache.clear()

    assert await cache.responses.size() == 0
    assert await cache.redirects.size() == 0


async def test_delete():
    cache = CacheBackend()
    mock_response = MagicMock()
    mock_response.history = [MagicMock(method='GET', url='test')]
    redirect_key = cache.create_key('GET', 'test')

    await cache.responses.write('key', mock_response)
    await cache.redirects.write(redirect_key, 'key')
    await cache.redirects.write('some_other_redirect', 'key')

    await cache.delete('key')
    assert await cache.responses.size() == 0
    assert await cache.redirects.size() == 1


# TODO
async def test_delete_url():
    pass


# TODO
async def test_delete_expired_responses():
    pass


# TODO
async def test_has_url():
    pass


# TODO
async def test_create_key():
    pass


@pytest.mark.parametrize(
    'method, status, disabled, expired, filter_return, expected_result',
    [
        ('GET', 200, False, False, True, True),
        ('DELETE', 200, False, False, True, False),
        ('GET', 502, False, False, True, False),
        ('GET', 200, True, False, True, False),
        ('GET', 200, False, True, True, False),
        ('GET', 200, False, False, False, False),
    ],
)
async def test_is_cacheable(method, status, disabled, expired, filter_return, expected_result):
    mock_response = MagicMock(
        method=method,
        status=status,
        is_expired=expired,
    )
    cache = CacheBackend()
    cache.filter_fn = lambda x: filter_return
    cache.disabled = disabled
    assert cache.is_cacheable(mock_response) is expected_result
