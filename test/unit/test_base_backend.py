from __future__ import annotations
from datetime import timedelta
import json
import pickle
from typing import Literal, cast
from unittest.mock import patch

import pytest
from yarl import URL

from aiohttp_client_cache import CachedResponse
from aiohttp_client_cache.backends import CacheBackend, DictCache, get_placeholder_backend
from aiohttp_client_cache.cache_control import utcnow
from aiohttp_client_cache.session import CachedSession
from test.conftest import httpbin

TEST_URL = 'https://test.com'


async def get_test_response(
    *,
    relative_url: str = '',
    is_expired: bool = False,
    method: Literal['GET', 'POST', 'DELETE'] = 'GET',
    request_body: str | None = None,
) -> CachedResponse:
    async with CachedSession() as session:
        if method == 'POST':
            session_method = session.post
            relative_url = 'post'
        elif method == 'GET':
            session_method = session.get
        elif method == 'DELETE':
            session_method = session.delete
            relative_url = 'delete'
        async with session_method(httpbin(relative_url), json=request_body) as cached_response:
            await cast(CachedResponse, cached_response).postprocess(
                (utcnow() - timedelta(minutes=1)) if is_expired else utcnow() + timedelta(minutes=1)
            )
            return cast(CachedResponse, cached_response)


def test_get_placeholder_backend():
    class TestBackend:
        def __init__(self):
            import nonexistent_module  # noqa: F401

    try:
        TestBackend()
    except ImportError as e:
        placeholder = get_placeholder_backend(e)

    # Initializing the placeholder class should re-raise the original ImportError
    with pytest.raises(ImportError):
        placeholder()


async def test_get_response__cache_response_hit():
    cache = CacheBackend()
    response = await get_test_response()
    await cache.responses.write('request-key', response)

    cached_response = cast(CachedResponse, await cache.get_response('request-key'))
    assert cached_response.from_cache is True
    cached_response.from_cache = False  # Reset the value to simplify comparing two instances.

    response._cache = {}
    cached_response._cache = {}
    response._content = None
    cached_response._content = None
    for k, v in cached_response.__dict__.items():
        assert v == getattr(response, k)

    # The same attributes, but two class instances.
    assert response != cached_response


async def test_get_response__cache_redirect_hit():
    # Set up a cache with a couple cached items and a redirect
    cache = CacheBackend()
    response = await get_test_response()
    await cache.responses.write('request-key', response)
    await cache.redirects.write('redirect-key', 'request-key')

    cached_response = cast(CachedResponse, await cache.get_response('redirect-key'))
    assert cached_response.from_cache is True
    cached_response.from_cache = False  # Reset the value to simplify comparing two instances.

    response._cache = {}
    cached_response._cache = {}
    response._content = None
    cached_response._content = None
    for k, v in cached_response.__dict__.items():
        assert v == getattr(response, k)

    # The same attributes, but two class instances.
    assert cached_response != response


@patch.object(CacheBackend, 'delete')
async def test_get_response__cache_miss(mock_delete):
    cache = CacheBackend()

    response_1 = await cache.get_response('nonexistent-key')
    assert response_1 is None
    mock_delete.assert_not_called()


@patch.object(CacheBackend, 'delete')
@patch.object(CacheBackend, 'is_cacheable', return_value=False)
async def test_get_response__cache_expired(mock_is_cacheable, mock_delete):
    cache = CacheBackend()
    mock_response = await get_test_response(is_expired=True)
    await cache.responses.write('request-key', mock_response)

    response = await cache.get_response('request-key')
    assert response is None
    mock_delete.assert_called_with('request-key')


@pytest.mark.parametrize('error_type', [AttributeError, KeyError, TypeError, pickle.PickleError])
@patch.object(CacheBackend, 'delete')
@patch.object(DictCache, 'read')
async def test_get_response__cache_invalid(mock_read, mock_delete, error_type):
    cache = CacheBackend()
    mock_read.side_effect = error_type
    mock_response = await get_test_response()
    await cache.responses.write('request-key', mock_response)

    response = await cache.get_response('request-key')
    assert response is None
    mock_delete.assert_not_called()


@patch.object(DictCache, 'read', return_value=object())
async def test_get_response__quiet_serde_error(mock_read):
    """Test for a quiet deserialization error in which no errors are raised but attributes are
    missing
    """
    cache = CacheBackend()
    mock_response = await get_test_response()
    await cache.responses.write('request-key', mock_response)

    response = await cache.get_response('request-key')
    assert response is None


async def test_save_response():
    cache = CacheBackend()
    mock_response = await get_test_response(relative_url='redirect-to?url=anything&status_code=200')
    redirect_key = cache.create_key('GET', httpbin('redirect-to?url=anything&status_code=200'))

    await cache.save_response(mock_response, 'key')
    cached_response = await cache.responses.read('key')
    assert cached_response and isinstance(cached_response, CachedResponse)
    assert await cache.redirects.read(redirect_key) == 'key'


async def test_save_response__manual_save():
    """Manually save a response with no cache key provided"""
    cache = CacheBackend()
    mock_response = await get_test_response()

    await cache.save_response(mock_response)
    cached_response = [r async for r in cache.responses.values()][0]
    assert cached_response and isinstance(cached_response, CachedResponse)


async def test_clear():
    cache = CacheBackend()
    await cache.responses.write('key', 'value')
    await cache.redirects.write('key', 'value')
    await cache.clear()

    assert await cache.responses.size() == 0
    assert await cache.redirects.size() == 0


async def test_delete():
    cache = CacheBackend()
    mock_response = await get_test_response(relative_url='redirect-to?url=anything&status_code=200')
    redirect_key = cache.create_key('GET', httpbin('redirect-to?url=anything&status_code=200'))

    await cache.responses.write('key', mock_response)
    await cache.redirects.write(redirect_key, 'key')
    await cache.redirects.write('some_other_redirect', 'key')

    await cache.delete('key')
    assert await cache.responses.size() == 0
    assert await cache.redirects.size() == 1


async def test_delete_expired_responses():
    cache = CacheBackend()
    await cache.responses.write('request-key-1', await get_test_response(is_expired=False))
    await cache.responses.write('request-key-2', await get_test_response(is_expired=True))

    assert await cache.responses.size() == 2
    await cache.delete_expired_responses()
    assert await cache.responses.size() == 1


async def test_delete_url():
    cache = CacheBackend()
    response = await get_test_response()
    cache_key = cache.create_key('GET', TEST_URL, params={'param': 'value'})

    await cache.responses.write(cache_key, response)
    assert await cache.responses.size() == 1
    await cache.delete_url(TEST_URL, params={'param': 'value'})
    assert await cache.responses.size() == 0


async def test_has_url():
    cache = CacheBackend()
    response = await get_test_response()
    cache_key = cache.create_key('GET', TEST_URL, params={'param': 'value'})

    await cache.responses.write(cache_key, response)
    assert await cache.has_url(TEST_URL, params={'param': 'value'})
    assert not await cache.has_url('https://test.com/some_other_path')


@patch('aiohttp_client_cache.backends.base.create_key')
async def test_create_key(mock_create_key):
    """Actual logic is in cache_keys module; just test to make sure it gets called correctly"""
    headers = {'key': 'value'}
    ignored_params = ['ignored']
    cache = CacheBackend(include_headers=True, ignored_params=ignored_params)

    cache.create_key('GET', 'https://test.com', headers=headers)
    mock_create_key.assert_called_with(
        'GET',
        'https://test.com',
        include_headers=True,
        ignored_params=set(ignored_params),
        headers=headers,
    )


async def test_get_urls():
    cache = CacheBackend()
    for i in range(7):
        mock_response = await get_test_response(relative_url=f'anything/{i}')
        await cache.responses.write(f'request-key-{i}', mock_response)

    urls = {url async for url in cache.get_urls()}
    assert urls == {URL(f'{httpbin()}anything/{i}') for i in range(7)}


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
    mock_response = await get_test_response(
        relative_url='' if status == 200 else f'status/{status}',
        method=method,
        is_expired=expired,
    )
    cache = CacheBackend()
    cache.filter_fn = lambda x: filter_return
    cache.disabled = disabled
    assert await cache.is_cacheable(mock_response) is expected_result


@pytest.mark.parametrize(
    'method, status, disabled, expired, body, expected_result',
    [
        ('POST', 200, False, False, '{"content": "...", "success": true}', True),
        ('DELETE', 200, True, False, None, False),
        ('DELETE', 200, False, False, None, False),
        ('GET', 200, True, False, '{"content": "...", "success": false}', False),
        ('GET', 200, False, True, '{"content": "...", "success": true}', False),
    ],
)
async def test_is_cacheable_inspect(method, status, disabled, expired, body, expected_result):
    async def filter(resp):
        if not body or method == 'GET':
            return True
        json_resp = await resp.json()
        return json.loads(json_resp['json'])['success']

    response = await get_test_response(method=method, is_expired=expired, request_body=body)

    cache = CacheBackend(allowed_methods=('GET', 'POST'))
    cache.filter_fn = filter
    cache.disabled = disabled
    assert await cache.is_cacheable(response) is expected_result
