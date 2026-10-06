from __future__ import annotations

from datetime import datetime
from inspect import signature
from json import dumps
from unittest.mock import patch

import pytest
from aiohttp import ClientSession, web

from aiohttp_client_cache.backends import CacheBackend
from aiohttp_client_cache.cache_keys import create_key
from aiohttp_client_cache.session import CachedSession

requires_bytes_serializer = pytest.mark.skipif(
    'json_serialize_bytes' not in signature(ClientSession).parameters,
    reason='aiohttp does not support json_serialize_bytes',
)


class CapturedKey(Exception):
    pass


async def request_key(session: CachedSession, **kwargs) -> str:
    """Return the cache key that `session.post()` computes, without sending a request"""

    def capture(key, *args, **kw):
        raise CapturedKey(key)

    with patch.object(session.cache, 'create_cache_actions', side_effect=capture):
        with pytest.raises(CapturedKey) as exc_info:
            await session.post('https://example.com', **kwargs)
    return exc_info.value.args[0]


def serialize_bytes(body) -> bytes:
    """Stand-in for `orjson.dumps`, which handles `datetime` natively"""
    return dumps(body, default=datetime.isoformat).encode()


@pytest.mark.asyncio
@requires_bytes_serializer
async def test_session_json_serialize_bytes_is_used_for_cache_key():
    async with CachedSession(cache=CacheBackend(), json_serialize_bytes=serialize_bytes) as session:
        key = await request_key(session, json={'at': datetime(2026, 1, 2)})
    assert key == create_key(
        'POST',
        'https://example.com',
        json={'at': datetime(2026, 1, 2)},
        json_serialize=lambda body: serialize_bytes(body),
    )


@pytest.mark.asyncio
@requires_bytes_serializer
async def test_session_json_serialize_bytes_distinguishes_bodies():
    class Tagged(str):
        """Serialized identically to `str` by stdlib `json.dumps()`"""

    def serialize(body) -> bytes:
        return b'"tagged"' if isinstance(body, Tagged) else dumps(body).encode()

    async with CachedSession(cache=CacheBackend(), json_serialize_bytes=serialize) as session:
        assert await request_key(session, json=Tagged('x')) != await request_key(session, json='x')


def test_create_key_accepts_serializer_returning_bytes():
    key = create_key(
        'POST',
        'https://example.com',
        json={'a': 1},
        json_serialize=lambda body: dumps(body).encode(),
    )
    assert key == create_key('POST', 'https://example.com', json={'a': 1})


def test_create_key_serializes_bytes_json_with_configured_serializer():
    def serialize(body) -> str:
        return dumps({'bytes': body.decode()}) if isinstance(body, bytes) else dumps(body)

    assert create_key(
        'POST', 'https://example.com', json=b'false', json_serialize=serialize
    ) != create_key('POST', 'https://example.com', json=False, json_serialize=serialize)


@pytest.mark.asyncio
@requires_bytes_serializer
async def test_session_json_serialize_bytes_takes_precedence():
    def serialize(body) -> str:
        raise AssertionError('The string serializer should not be used')

    async with CachedSession(
        cache=CacheBackend(), json_serialize=serialize, json_serialize_bytes=serialize_bytes
    ) as session:
        key = await request_key(session, json={'a': 1})
    assert key == create_key('POST', 'https://example.com', json={'a': 1})


@pytest.mark.asyncio
async def test_session_json_serialize_fallback():
    def serialize(body) -> str:
        return dumps(body, default=datetime.isoformat)

    body = {'at': datetime(2026, 1, 2)}
    async with CachedSession(cache=CacheBackend(), json_serialize=serialize) as session:
        key = await request_key(session, json=body)
    assert key == create_key('POST', 'https://example.com', json=body, json_serialize=serialize)


def test_create_key_rejects_bytes_json_with_default_serializer():
    with pytest.raises(TypeError):
        create_key('POST', 'https://example.com', json=b'false')


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'serializer_option',
    [
        'json_serialize',
        pytest.param('json_serialize_bytes', marks=requires_bytes_serializer),
    ],
)
async def test_json_bytes_values_cache_separate_responses(aiohttp_server, serializer_option):
    received = []

    async def echo(request):
        body = await request.text()
        received.append(body)
        return web.Response(text=body, content_type='application/json')

    def serialize(body):
        body = {'bytes': body.decode()} if isinstance(body, bytes) else body
        serialized = dumps(body)
        return serialized.encode() if serializer_option == 'json_serialize_bytes' else serialized

    app = web.Application()
    app.router.add_post('/', echo)
    server = await aiohttp_server(app)
    cache = CacheBackend(allowed_methods=['POST'])
    async with CachedSession(cache=cache, **{serializer_option: serialize}) as session:
        for body, expected in [(b'false', {'bytes': 'false'}), (False, False)]:
            response = await session.post(server.make_url('/'), json=body)
            assert not response.from_cache
            assert await response.json() == expected
            cached_response = await session.post(server.make_url('/'), json=body)
            assert cached_response.from_cache
            assert await cached_response.json() == expected

    assert received == ['{"bytes": "false"}', 'false']


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'serializer_option',
    [
        'json_serialize',
        pytest.param('json_serialize_bytes', marks=requires_bytes_serializer),
    ],
)
async def test_session_url_helpers_use_session_json_serializer(aiohttp_server, serializer_option):
    async def echo(request):
        return web.Response(text=await request.text())

    def serialize(body):
        serialized = dumps(body, separators=(',', ':'))
        return serialized.encode() if serializer_option == 'json_serialize_bytes' else serialized

    app = web.Application()
    app.router.add_post('/', echo)
    server = await aiohttp_server(app)
    url = server.make_url('/')
    cache = CacheBackend(allowed_methods=['POST'])
    async with CachedSession(cache=cache, **{serializer_option: serialize}) as session:
        await session.post(url, json={'a': 1})
        async with CachedSession(cache=cache):
            assert await session.has_url(url, method='POST', json={'a': 1})
            await session.delete_url(url, method='POST', json={'a': 1})
        assert await cache.responses.size() == 0
