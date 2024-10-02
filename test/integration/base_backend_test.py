"""Common tests to run for all backends"""

from __future__ import annotations

import asyncio
import pickle
from contextlib import asynccontextmanager

from aiohttp import HttpVersion, RequestInfo
from multidict import CIMultiDictProxy, MultiDictProxy
from yarl import URL
from test.conftest import (
    ALL_METHODS,
    CACHE_NAME,
    HTTPBIN_FORMATS,
    HTTPBIN_METHODS,
    HTTPDATE_STR,
    assert_delta_approx_equal,
    httpbin,
    httpbin_custom,
)
from typing import Any, AsyncIterator, cast
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from async_timeout import timeout
from itsdangerous.exc import BadSignature
from itsdangerous.serializer import Serializer

from aiohttp_client_cache import CacheBackend, CachedSession
from aiohttp_client_cache.cache_control import utcnow
from aiohttp_client_cache.response import CachedResponse, CachedStreamReader

pytestmark = pytest.mark.asyncio


class BaseBackendTest:
    """Base class for testing cache backend classes"""

    backend_class: type[CacheBackend] = None  # type: ignore
    init_kwargs: dict[str, Any] = {}

    @asynccontextmanager
    async def init_session(self, clear=True, **kwargs) -> AsyncIterator[CachedSession]:
        session = await self._init_session(clear=clear, **kwargs)
        async with session:
            yield session

    async def _init_session(self, clear=True, **kwargs) -> CachedSession:
        kwargs.setdefault('allowed_methods', ALL_METHODS)
        cache = self.backend_class(CACHE_NAME, **self.init_kwargs, **kwargs)
        if clear:
            await cache.clear()

        return CachedSession(cache=cache, **self.init_kwargs, **kwargs)

    @pytest.mark.parametrize('method', HTTPBIN_METHODS)
    @pytest.mark.parametrize('field', ['params', 'data', 'json'])
    async def test_all_methods(self, field, method):
        """Test all relevant combinations of methods and data fields. Requests with different request
        params, data, or json should be cached under different keys.
        """
        url = httpbin(method.lower())
        async with self.init_session() as session:
            for params in [{'param_1': 1}, {'param_1': 2}, {'param_2': 2}]:
                response_1 = cast(
                    CachedResponse, await session.request(method, url, **{field: params})
                )
                assert response_1.from_cache is False
                response_2 = cast(
                    CachedResponse, await session.request(method, url, **{field: params})
                )
                assert response_2.from_cache is True

    @pytest.mark.parametrize('method', HTTPBIN_METHODS)
    @pytest.mark.parametrize('field', ['params', 'data', 'json', 'headers'])
    async def test_all_methods__ignore_parameters(self, field, method):
        """Test all relevant combinations of methods and data fields. Requests with different request
        params, data, or json should not be cached under different keys based on an ignored param.
        """
        params_1 = {'ignored': 'value1', 'not ignored': 'value1'}
        params_2 = {'ignored': 'value2', 'not ignored': 'value1'}
        params_3 = {'ignored': 'value2', 'not ignored': 'value2'}
        url = httpbin(method.lower())

        async with self.init_session(
            allowed_codes=(200, 400), ignored_params=['ignored'], include_headers=True
        ) as session:
            response_1 = cast(
                CachedResponse, await session.request(method, url, **{field: params_1})
            )
            assert response_1.from_cache is False
            response_2 = cast(
                CachedResponse, await session.request(method, url, **{field: params_1})
            )
            assert response_2.from_cache is True
            response_3 = cast(
                CachedResponse, await session.request(method, url, **{field: params_2})
            )
            assert response_3.from_cache is True
            await session.request(method, url, params={'a': 'b'})
            response_4 = cast(
                CachedResponse, await session.request(method, url, **{field: params_3})
            )
            assert response_4.from_cache is False

    async def test_gather(self):
        # limit the maximum number of concurrent reads to 100 to avoid
        # problems with too many open files when using a FileBackend
        sem = asyncio.Semaphore(100)

        urls = [httpbin(f'get?page={i}') for i in range(500)]

        async def get_url(mysession, url):
            async with sem:
                return await mysession.get(url)

        async with self.init_session() as session:
            tasks = [asyncio.create_task(get_url(session, url)) for url in urls]
            responses = await asyncio.gather(*tasks)
            assert all(r.from_cache is False for r in responses)

            tasks = [asyncio.create_task(get_url(session, url)) for url in urls]
            responses = await asyncio.gather(*tasks)
            assert all(r.from_cache is True for r in responses)

    async def test_without_contextmanager(self):
        """Test that the cache backend can be safely used without the CachedSession contextmanager.
        An "unclosed ClientSession" warning is expected here, however.
        """
        # Timeout to avoid hanging if the test fails
        async with timeout(5.0):
            session = await self._init_session()
            await session.get(httpbin('get'))
            del session

            session = await self._init_session(clear=False)
            r = cast(CachedResponse, await session.get(httpbin('get')))
            assert r.from_cache is True

    async def test_request__expire_after(self):
        async with self.init_session() as session:
            await session.get(httpbin('get'), expire_after=1)
            response = cast(CachedResponse, await session.get(httpbin('get'), expire_after=1))
            assert response.from_cache is True

            # After 1 second, the response should be expired, and a new one should be fetched
            await asyncio.sleep(1)
            response = cast(CachedResponse, await session.get(httpbin('get'), expire_after=1))
            print(response.expires)
            assert response.from_cache is False

    async def test_delete_expired_responses(self):
        async with self.init_session(expire_after=1) as session:
            # Populate the cache with several responses that should expire immediately
            for response_format in HTTPBIN_FORMATS:
                await session.get(httpbin(response_format))
            await session.get(httpbin('redirect/1'))
            await asyncio.sleep(1)

            # Cache a response and some redirects, which should be the only non-expired cache items
            session.cache.expire_after = -1
            await session.get(httpbin('get'))
            await session.get(httpbin('redirect/3'))
            assert await session.cache.redirects.size() == 4
            await session.cache.delete_expired_responses()

            assert await session.cache.responses.size() == 2
            assert await session.cache.redirects.size() == 3
            assert not await session.cache.has_url(httpbin('redirect/1'))
            assert not any([await session.cache.has_url(httpbin(f)) for f in HTTPBIN_FORMATS])

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
            response_1 = cast(
                CachedResponse, await session.get(httpbin('get'), headers={'key': 'value'})
            )
            assert response_1.from_cache is False
            response_2 = cast(
                CachedResponse, await session.get(httpbin('get'), headers={'key': 'value'})
            )
            assert response_2.from_cache is True

    async def test_streaming_requests(self):
        """Test that streaming requests work both for the original and cached responses"""
        async with self.init_session() as session:
            for _ in range(2):
                response = cast(CachedResponse, await session.get(httpbin('stream-bytes/64')))
                lines = [line async for line in response.content]
                assert len(b''.join(lines)) == 64

                # Can read multiple times.
                assert len(await response.read()) == 64
                assert len(await response.read()) == 64

                response.reset()
                chunks = [c async for (c, _) in response.content.iter_chunks()]
                assert len(b''.join(chunks)) == 64
                chunks = [c async for (c, _) in response.content.iter_chunks()]
                assert len(b''.join(chunks)) == 0
                response.reset()

                chunks = [c async for c in response.content.iter_chunked(2)]
                assert len(b''.join(chunks)) == 64
                chunks = [c async for c in response.content.iter_chunked(2)]
                assert len(b''.join(chunks)) == 0
                response.reset()

                chunks = [c async for c in response.content.iter_any()]
                assert len(b''.join(chunks)) == 64
                chunks = [c async for c in response.content.iter_any()]
                assert len(b''.join(chunks)) == 0
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
            now = utcnow()
            await session.get(httpbin('cache/60'), headers=request_headers)
            response = cast(
                CachedResponse, await session.get(httpbin('cache/60'), headers=request_headers)
            )

        if expected_expiration is None:
            assert response.expires is None
        else:
            assert_delta_approx_equal(now, response.expires, expected_expiration)  # type: ignore[arg-type]

    async def test_request__cache_control_disabled(self):
        """By default, no-cache request headers should be ignored"""
        async with self.init_session() as session:
            headers = {'Cache-Control': 'no-cache'}
            await session.get(httpbin('get'), headers=headers)
            response = cast(CachedResponse, await session.get(httpbin('get'), headers=headers))
            assert response.from_cache is True

    async def test_request__skip_cache_read(self):
        """With cache_control=True, no-cache request header should skip reading, but still write to
        the cache
        """
        async with self.init_session(cache_control=True) as session:
            headers = {'Cache-Control': 'no-cache'}
            await session.get(httpbin('get'), headers=headers)
            response = cast(CachedResponse, await session.get(httpbin('get'), headers=headers))

            assert response.from_cache is False
            assert await session.cache.responses.size() == 1
            response = cast(CachedResponse, await session.get(httpbin('get')))
            assert response.from_cache is True

    @pytest.mark.parametrize('directive', ['max-age=0', 'no-store'])
    async def test_request__skip_cache_read_write(self, directive):
        """max-age=0 and no-store request headers should skip both reading from and writing to the cache"""
        async with self.init_session(cache_control=True) as session:
            headers = {'Cache-Control': directive}
            await session.get(httpbin('get'), headers=headers)
            response = cast(CachedResponse, await session.get(httpbin('get'), headers=headers))

            assert response.from_cache is False
            assert await session.cache.responses.size() == 0

            await session.get(httpbin('get'))
            assert (cast(CachedResponse, await session.get(httpbin('get')))).from_cache is True

    async def test_response__skip_cache_write(self):
        """max-age=0 response header should skip writing to the cache"""
        async with self.init_session(cache_control=True) as session:
            await session.get(httpbin('cache/0'))
            response = cast(CachedResponse, await session.get(httpbin('cache/0')))

            assert response.from_cache is False
            assert await session.cache.responses.size() == 0

    async def test_cookies_with_redirect(self):
        async with self.init_session(cache_control=True) as session:
            await session.get(httpbin('cookies/set?test_cookie=value'))
            session.cookie_jar.clear()
            await session.get(httpbin('cookies/set?test_cookie=value'))

        cookies = session.cookie_jar.filter_cookies(httpbin())
        assert cookies['test_cookie'].value == 'value'

    async def test_autoclose(self):
        async with self.init_session(autoclose=True) as session:
            mock_close = MagicMock(wraps=session.cache.close)
            session.cache.close = mock_close  # type: ignore[method-assign]
            await session.get(httpbin('get'))
        mock_close.assert_called_once()

    async def test_autoclose__disabled(self):
        async with self.init_session(autoclose=False) as session:
            mock_close = MagicMock(wraps=session.cache.close)
            session.cache.close = mock_close  # type: ignore[method-assign]
            await session.get(httpbin('get'))
        mock_close.assert_not_called()
        # explicitly call close after the test has completed
        # to properly shutdown the cache backend
        await session.cache.close()

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

    async def test_disabled(self):
        """With a disabled CachedSession, responses should not come from the cache
        and the cache should not be modified
        """
        async with self.init_session() as session:
            # first request shall populate the cache
            response = cast(CachedResponse, await session.request('GET', httpbin('cache/0')))

            assert response.from_cache is False
            assert await session.cache.responses.size() == 1

            # second request shall come from the cache
            response = cast(CachedResponse, await session.request('GET', httpbin('cache/0')))

            assert response.from_cache is True
            assert await session.cache.responses.size() == 1

            # now disable the cache, the response should not come from the cache
            # but the cache should be unmodified afterward.
            async with session.disabled():
                response = cast(CachedResponse, await session.request('GET', httpbin('cache/0')))

                assert response.from_cache is False
                assert await session.cache.responses.size() == 1

    async def test_conditional_request(self):
        """Test that conditional requests using refresh=True work.
        The `/cache` endpoint returns proper ETag header and responds to a request
        with an If-None-Match header with a 304 response.
        """

        async with self.init_session() as session:
            # mock the _refresh_cached_response method to verify
            # that a conditional request is being made
            from unittest.mock import AsyncMock

            mock_refresh = AsyncMock(wraps=session._refresh_cached_response)
            session._refresh_cached_response = mock_refresh  # type: ignore[method-assign]

            response = cast(CachedResponse, await session.get(httpbin('cache')))
            assert response.from_cache is False
            etag = response.headers['Etag']
            assert etag is not None
            mock_refresh.assert_not_awaited()

            response = cast(CachedResponse, await session.get(httpbin('cache'), refresh=True))
            assert response.from_cache is True
            assert etag == response.headers['Etag']
            mock_refresh.assert_awaited_once()

    async def test_conditional_request_changed(self):
        """Test that conditional requests using refresh=True work.
        The `/cache/<value>` endpoint will return a different ETag ever <value> s.
        """

        async with self.init_session() as session:
            # mock the _refresh_cached_response method to verify
            # that a conditional request is being made
            from unittest.mock import AsyncMock

            mock_refresh = AsyncMock(wraps=session._refresh_cached_response)
            session._refresh_cached_response = mock_refresh  # type: ignore[method-assign]

            response = cast(CachedResponse, await session.get(httpbin_custom('cache/1')))
            assert response.from_cache is False
            etag = response.headers['Etag']
            assert etag is not None
            mock_refresh.assert_not_awaited()

            await asyncio.sleep(2)
            # after 2s the ETag should have been expired and the server should respond
            # with a 200 response rather than a 304.

            response = cast(
                CachedResponse, await session.get(httpbin_custom('cache/1'), refresh=True)
            )
            assert response.from_cache is False
            assert etag != response.headers['Etag']
            mock_refresh.assert_awaited_once()

    async def test_no_support_for_conditional_request(self):
        """Test that conditional requests using refresh=True work even when the
        cached response / server does not support conditional requests. In this case
        the cached response shall be returned as if no refresh=True option would
        have been passed in.
        The `/cache/<int>` endpoint returns no ETag header and just returns a normal 200 response.
        """

        async with self.init_session() as session:
            # mock the _refresh_cached_response method to verify
            # that a conditional request is being made
            from unittest.mock import AsyncMock

            mock_refresh = AsyncMock(wraps=session._refresh_cached_response)
            session._refresh_cached_response = mock_refresh  # type: ignore[method-assign]

            response = cast(CachedResponse, await session.get(httpbin('cache/10')))
            assert response.from_cache is False
            assert response.headers.get('Etag') is None
            mock_refresh.assert_not_awaited()

            response = cast(CachedResponse, await session.get(httpbin('cache/10'), refresh=True))
            assert response.from_cache is True
            assert response.headers.get('Etag') is None
            mock_refresh.assert_awaited_once()

    async def test_concurrent(self):
        urls = [httpbin('get?page=0') for _ in range(100)]

        async with self.init_session() as session:
            tasks = [session.get(url) for url in urls]
            responses = await asyncio.gather(*tasks)
            assert len(responses) == 100
            assert [cast(CachedResponse, r).from_cache for r in responses].count(False) == 1

    async def test_response_attributes(self):
        url = 'http://0.0.0.0:8080/json'
        async with self.init_session() as session:
            response_1 = cast(CachedResponse, await session.get(url))
            uncached_response_attributes = response_1.__dict__

            for k in uncached_response_attributes:
                v = getattr(response_1, k)
                if k in {'_ClientResponse__writer'}:
                    continue
                if k in {
                    'expires',
                    'from_cache',
                    'cookies',
                    '_continue',
                    '_history',
                    '_traces',
                    '_session',
                    '_protocol',
                    '_connection',
                }:
                    assert not v
                else:
                    assert v

            assert isinstance(response_1._content, CachedStreamReader)
            assert isinstance(response_1.content, CachedStreamReader)
            assert isinstance(response_1.version, HttpVersion)
            assert isinstance(response_1.status, int)
            assert isinstance(response_1.reason, str)
            assert isinstance(response_1.headers, CIMultiDictProxy)
            assert isinstance(response_1.raw_headers, tuple)
            assert isinstance(response_1.url, URL)
            assert isinstance(response_1.real_url, URL)
            assert isinstance(response_1.host, str)
            assert isinstance(response_1.request_info, RequestInfo)
            assert response_1.content_disposition is None  # Covered in `test_content_disposition`.
            assert response_1.connection is None
            assert isinstance(response_1.history, tuple)
            assert isinstance(response_1.links, MultiDictProxy)
            assert response_1.closed is True
            assert response_1.ok is True
            response_1.raise_for_status()
            assert response_1.get_encoding() == 'utf-8'
            assert response_1.headers['Content-Type'] == 'application/json'

            # Loaded from the cache deserialized response has all attributes.
            response_2 = cast(CachedResponse, await session.get(url))

            cached_response_missing_attributes = {
                '_request_info',
                '_timer',
                '_loop',
                '_resolve_charset',
                '_protocol',
            }

            for k in uncached_response_attributes:
                if k in cached_response_missing_attributes:
                    continue
                if k == '_content':
                    assert getattr(response_2, k) is None
                    continue
                v = getattr(response_2, k)
                if k in {'_ClientResponse__writer'}:
                    continue
                elif k in {
                    'expires',
                    'cookies',
                    '_continue',
                    '_history',
                    '_traces',
                    '_session',
                    '_protocol',
                    '_connection',
                }:
                    assert not v
                else:
                    assert v

            assert response_2._content is None
            assert isinstance(response_2.content, CachedStreamReader)
            assert isinstance(response_2._content, CachedStreamReader)
            assert isinstance(response_2.version, HttpVersion)  # type: ignore[unreachable]
            assert isinstance(response_2.status, int)
            assert isinstance(response_2.reason, str)
            assert isinstance(response_2.headers, CIMultiDictProxy)
            assert isinstance(response_2.raw_headers, tuple)
            assert isinstance(response_2.url, URL)
            assert isinstance(response_2.real_url, URL)
            assert isinstance(response_2.host, str)
            assert isinstance(response_2.request_info, RequestInfo)
            assert response_2.content_disposition is None  # Covered in `test_content_disposition`.
            assert response_2.connection is None
            assert isinstance(response_2.history, tuple)
            assert isinstance(response_2.links, MultiDictProxy)
            assert response_2.closed is True
            assert response_2.ok is True
            response_2.raise_for_status()
            assert response_2.get_encoding() == 'utf-8'
            assert response_2.headers['Content-Type'] == 'application/json'

            assert await response_1.content.read() == await response_2.content.read()
            assert response_1.version == response_2.version
            assert response_1.status == response_2.status
            assert response_1.reason == response_2.reason
            assert response_1.headers == response_2.headers
            assert response_1.raw_headers == response_2.raw_headers
            assert response_1.url == response_2.url
            assert response_1.real_url == response_2.real_url
            assert response_1.host == response_2.host
            assert response_1.request_info == response_2.request_info
            assert response_1.history == response_2.history
            assert response_1.links == response_2.links
