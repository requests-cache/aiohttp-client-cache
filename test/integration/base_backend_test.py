"""Common tests to run for all backends"""
import pickle
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator, Dict, Type
from uuid import uuid4

import pytest
from itsdangerous.exc import BadSignature
from itsdangerous.serializer import Serializer

from aiohttp_client_cache import CacheBackend, CachedSession
from test.conftest import (
    ALL_METHODS,
    CACHE_NAME,
    HTTPBIN_METHODS,
    HTTPDATE_STR,
    assert_delta_approx_equal,
    from_cache,
    httpbin,
)

pytestmark = pytest.mark.asyncio


class BaseBackendTest:
    """Base class for testing cache backend classes"""

    backend_class: Type[CacheBackend] = None  # type: ignore
    init_kwargs: Dict[str, Any] = {}

    @asynccontextmanager
    async def init_session(self, clear=True, **kwargs) -> AsyncIterator[CachedSession]:
        kwargs.setdefault('allowed_methods', ALL_METHODS)
        # kwargs.setdefault('serializer', 'pickle')
        cache = self.backend_class(CACHE_NAME, **self.init_kwargs, **kwargs)
        if clear:
            await cache.clear()

        async with CachedSession(cache=cache, **self.init_kwargs, **kwargs) as session:
            yield session

    @pytest.mark.parametrize('method', HTTPBIN_METHODS)
    @pytest.mark.parametrize('field', ['params', 'data', 'json'])
    async def test_all_methods(self, field, method):
        """Test all relevant combinations of methods and data fields. Requests with different request
        params, data, or json should be cached under different keys.
        """
        url = httpbin(method.lower())
        async with self.init_session() as session:
            for params in [{'param_1': 1}, {'param_1': 2}, {'param_2': 2}]:
                response_1 = await session.request(method, url, **{field: params})
                response_2 = await session.request(method, url, **{field: params})
                assert not from_cache(response_1) and from_cache(response_2)

    @pytest.mark.parametrize('method', HTTPBIN_METHODS)
    @pytest.mark.parametrize('field', ['params', 'data', 'json'])
    async def test_all_methods__ignore_parameters(self, field, method):
        """Test all relevant combinations of methods and data fields. Requests with different request
        params, data, or json should not be cached under different keys based on an ignored param.
        """
        params_1 = {'ignored': 1, 'not ignored': 1}
        params_2 = {'ignored': 2, 'not ignored': 1}
        params_3 = {'ignored': 2, 'not ignored': 2}
        url = httpbin(method.lower())

        async with self.init_session(ignored_params=['ignored']) as session:
            response_1 = await session.request(method, url, **{field: params_1})
            response_2 = await session.request(method, url, **{field: params_1})
            response_3 = await session.request(method, url, **{field: params_2})
            await session.request(method, url, params={'a': 'b'})
            response_4 = await session.request(method, url, **{field: params_3})

        assert not from_cache(response_1) and from_cache(response_2)
        assert from_cache(response_3) and not from_cache(response_4)

    @pytest.mark.parametrize('n_redirects', range(1, 5))
    @pytest.mark.parametrize('endpoint', ['redirect', 'absolute-redirect', 'relative-redirect'])
    async def test_redirects(self, endpoint, n_redirects):
        """Test all types of redirect endpoints with different numbers of consecutive redirects"""
        async with self.init_session() as session:
            await session.get(httpbin(f'{endpoint}/{n_redirects}'))
            await session.get(httpbin('get'))
            assert await session.cache.redirects.size() == n_redirects

    async def test_include_headers(self):
        async with self.init_session(include_headers=True) as session:
            await session.get(httpbin('get'))
            response_1 = await session.get(httpbin('get'), headers={'key': 'value'})
            response_2 = await session.get(httpbin('get'), headers={'key': 'value'})

        assert not from_cache(response_1) and from_cache(response_2)

    async def test_streaming_requests(self):
        """Test that streaming requests work both for the original and cached responses"""
        async with self.init_session() as session:
            for _ in range(2):
                response = await session.get(httpbin('stream-bytes/64'))
                lines = [line async for line in response.content]
                assert len(b''.join(lines)) == 64

            # Test some additional methods on the cached response
            response.reset()
            chunks = [c async for (c, _) in response.content.iter_chunks()]
            assert len(b''.join(chunks)) == 64
            response.reset()

            chunks = [c async for c in response.content.iter_chunked(2)]
            assert len(b''.join(chunks)) == 64
            response.reset()

            chunks = [c async for c in response.content.iter_any()]
            assert len(b''.join(chunks)) == 64
            response.reset()

            # readany() should return empty bytes after being consumed
            assert len(await response.content.readany()) == 64
            assert await response.content.readany() == b''

    async def test_streaming_request__ignored(self):
        """If a streaming request is filtered out (expire_after=0), its body should be readable as usual"""
        async with self.init_session(expire_after=0) as session:
            response = await session.get(httpbin('stream-bytes/64'))
            lines = [line async for line in response.content]
            assert len(b''.join(lines)) == 64

    @pytest.mark.parametrize(
        'request_headers, expected_expiration',
        [
            ({}, 60),
            ({'Cache-Control': 'max-age=360'}, 360),
            ({'Cache-Control': 'no-store'}, None),
            ({'Expires': HTTPDATE_STR, 'Cache-Control': 'max-age=360'}, 360),
        ],
    )
    async def test_cache_control__expiration(self, request_headers, expected_expiration):
        """Test cache headers for both requests and responses. The `/cache/{seconds}` endpoint returns
        Cache-Control headers, which should be used unless request headers are sent.
        """
        async with self.init_session() as session:
            session.cache.cache_control = True
            now = datetime.utcnow()
            await session.get(httpbin('cache/60'), headers=request_headers)
            response = await session.get(httpbin('cache/60'), headers=request_headers)

        if expected_expiration is None:
            assert response.expires is None
        else:
            assert_delta_approx_equal(now, response.expires, expected_expiration)

    async def test_request__cache_control_disabled(self):
        """By default, no-cache request headers should be ignored"""
        async with self.init_session() as session:
            headers = {'Cache-Control': 'no-cache'}
            await session.get(httpbin('get'), headers=headers)
            response = await session.get(httpbin('get'), headers=headers)
            assert response.from_cache is True

    async def test_request__skip_cache_read(self):
        """With cache_control=True, no-cache request header should skip reading, but still write to
        the cache
        """
        async with self.init_session(cache_control=True) as session:
            headers = {'Cache-Control': 'no-cache'}
            await session.get(httpbin('get'), headers=headers)
            response = await session.get(httpbin('get'), headers=headers)

            assert response.from_cache is False
            assert await session.cache.responses.size() == 1
            assert (await session.get(httpbin('get'))).from_cache is True

    @pytest.mark.parametrize('directive', ['max-age=0', 'no-store'])
    async def test_request__skip_cache_read_write(self, directive):
        """max-age=0 and no-store request headers should skip both reading from and writing to the cache"""
        async with self.init_session(cache_control=True) as session:
            headers = {'Cache-Control': directive}
            await session.get(httpbin('get'), headers=headers)
            response = await session.get(httpbin('get'), headers=headers)

            assert response.from_cache is False
            assert await session.cache.responses.size() == 0

            await session.get(httpbin('get'))
            assert (await session.get(httpbin('get'))).from_cache is True

    async def test_response__skip_cache_write(self):
        """max-age=0 response header should skip writing to the cache"""
        async with self.init_session(cache_control=True) as session:
            await session.get(httpbin('cache/0'))
            response = await session.get(httpbin('cache/0'))

            assert response.from_cache is False
            assert await session.cache.responses.size() == 0

    async def test_serializer__pickle(self):
        """Without a secret key, plain pickle should be used"""
        async with self.init_session() as session:
            assert session.cache.responses._serializer == pickle

    async def test_serializer__itsdangerous(self):
        """With a secret key, itsdangerous should be used"""
        secret_key = str(uuid4())
        async with self.init_session(secret_key=secret_key) as session:
            assert isinstance(session.cache.responses._serializer, Serializer)

            # Simple serialize/deserialize round trip
            await session.cache.responses.write('key', 'value')
            assert (await session.cache.responses.read('key')) == 'value'

            # Without the same signing key, the item shouldn't be considered safe to deserialize
            session.cache.responses._serializer.secret_keys = ['a different key']
            with pytest.raises(BadSignature):
                await session.cache.responses.read('key')
