"""The cache_keys module is mostly covered indirectly via other tests.
This just contains tests for some extra edge cases not covered elsewhere.
"""

from __future__ import annotations

import tracemalloc
from copy import copy
from decimal import Decimal
from json import dumps

import pytest
from aiohttp import web
from multidict import MultiDict

from aiohttp_client_cache.backends import CacheBackend
from aiohttp_client_cache.cache_keys import create_key
from aiohttp_client_cache.session import CachedSession

BODY_SIZE = 10 * 1024 * 1024


@pytest.mark.parametrize(
    'url, params',
    [
        ('https://example.com?foo=bar&param=1', None),
        ('https://example.com?foo=bar&param=1', {}),
        ('https://example.com?foo=bar&param=1&', {}),
        ('https://example.com?param=1&foo=bar', {}),
        ('https://example.com?param=1', {'foo': 'bar'}),
        ('https://example.com?foo=bar', {'param': '1'}),
        ('https://example.com', {'param': '1', 'foo': 'bar'}),
        ('https://example.com', {'foo': 'bar', 'param': '1'}),
        ('https://example.com', {'foo': 'bar', 'param': 1}),
        ('https://example.com?', {'foo': 'bar', 'param': '1'}),
        ('https://example.com?', (('foo', 'bar'), ('param', '1'))),
    ],
)
def test_normalize_url_params(url, params):
    """All of these variations should produce the same cache key"""
    original_params = copy(params) if params is not None else params
    cache_key = '17ac68009d0c70c25e7a7b1810a89683a84d437b009c0900c02fb2bb5b18c9f5'
    assert create_key('GET', url, params=params) == cache_key
    assert original_params == params  # Make sure we didn't modify the original params object


@pytest.mark.parametrize(
    'url, params',
    [
        ('https://example.com?param1=value1&param1=value2', {}),
        ('https://example.com?param1=value1', {'param1': 'value2'}),
        ('https://example.com', (('param1', 'value1'), ('param1', 'value2'))),
        ('https://example.com', MultiDict((('param1', 'value1'), ('param1', 'value2')))),
    ],
)
def test_encode_duplicate_params(url, params):
    """All means of providing request params with duplicate parameter names should result in a
    cache key distinct from a request with only one of that parameter name.
    """
    assert (
        create_key('GET', url, params=params)
        != create_key('GET', 'http://url.com?param1=value1')
        != create_key('GET', 'http://url.com?param1=value2')
    )


@pytest.mark.parametrize(
    'field, body',
    [
        ('data', {'foo': 'bar'}),
        ('json', {'foo': 'bar'}),
        ('data', '{"foo": "bar"}'),
        ('json', '{"foo": "bar"}'),
        ('data', b'{"foo": "bar"}'),
    ],
)
def test_encode_request_body(body, field):
    """JSON values and raw data bodies should produce cache keys"""
    cache_key = create_key('GET', 'https://example.com', **{field: body})
    assert isinstance(cache_key, str)


@pytest.mark.parametrize(
    'body_1, body_2',
    [
        ({'a': 'b&c=d'}, {'a': 'b', 'c': 'd'}),
        ({'a=b': 'c'}, {'a': 'b=c'}),
        ({'a': 1}, {'a': '1'}),
        ({'a': True}, {'a': 'True'}),
        ({'a': None}, {'a': 'None'}),
        ({'a': {'b': 1}}, {'a': "{'b': 1}"}),
        ({'a': [1]}, {'a': '[1]'}),
        ([1], '[1]'),
        (False, 0),
        ({}, []),
        ({}, None),
        ('', False),
    ],
)
def test_json_cache_keys_distinguish_bodies(body_1, body_2):
    assert create_key('POST', 'https://example.com', json=body_1) != create_key(
        'POST', 'https://example.com', json=body_2
    )


def test_json_cache_keys_preserve_object_order():
    assert create_key('POST', 'https://example.com', json={'a': 1, 'b': 2}) == create_key(
        'POST', 'https://example.com', json={'b': 2, 'a': 1}
    )


def test_json_cache_keys_preserve_ignored_parameters():
    body = {'ignored': 'first', 'value': 1}
    assert create_key(
        'POST', 'https://example.com', json=body, ignored_params=['ignored']
    ) == create_key(
        'POST',
        'https://example.com',
        json={'value': 1, 'ignored': 'second'},
        ignored_params=['ignored'],
    )
    assert body == {'ignored': 'first', 'value': 1}


def test_json_cache_keys_accept_mixed_object_keys():
    assert isinstance(create_key('POST', 'https://example.com', json={1: 'a', 'b': 2}), str)


@pytest.mark.parametrize('key, alias', [(False, 'false'), (True, 'true'), (None, 'null')])
def test_json_cache_keys_preserve_aliased_key_order(key, alias):
    assert create_key('POST', 'https://example.com', json={key: 1, alias: 2}) != create_key(
        'POST', 'https://example.com', json={alias: 2, key: 1}
    )


def test_json_cache_keys_use_custom_serializer():
    def serialize(body):
        return dumps(body, default=float)

    decimal_key = create_key(
        'POST', 'https://example.com', json={'a': Decimal('1.5')}, json_serialize=serialize
    )
    assert decimal_key == create_key('POST', 'https://example.com', json={'a': 1.5})
    assert decimal_key != create_key('POST', 'https://example.com', json={'a': '1.5'})


@pytest.mark.parametrize(
    'request_1, request_2',
    [
        ({'data': b'false'}, {'json': False}),
        ({'data': '"a"'}, {'json': 'a'}),
        ({'data': b'x=1'}, {'headers': {'x': '1'}}),
    ],
)
def test_cache_key_components_do_not_run_together(request_1, request_2):
    assert create_key(
        'POST', 'https://example.com', include_headers=True, **request_1
    ) != create_key('POST', 'https://example.com', include_headers=True, **request_2)


@pytest.mark.parametrize(
    'data_1, data_2',
    [
        (b'x', 'x'),
        ({'a': 1}, 'a=1'),
        ({'a': 'b&c=d'}, {'a': 'b', 'c': 'd'}),
        ({}, b''),
        (b'', ''),
        ('', None),
        ({'a': b'x'}, {'a': 'x'}),
        ({'a': b'x', 'b': 'y'}, {'a': b'x', 'b': b'y'}),
        ({'a': [1, 2]}, {'a': '[1, 2]'}),
        ([('a', 'x')], "[('a', 'x')]"),
    ],
)
def test_data_cache_keys_distinguish_bodies(data_1, data_2):
    assert create_key('POST', 'https://example.com', data=data_1) != create_key(
        'POST', 'https://example.com', data=data_2
    )


@pytest.mark.parametrize(
    'data_1, data_2',
    [
        (bytearray(b'x'), b'x'),
        ({'a': 1}, {'a': '1'}),
        ({'a': '1', 'b': '2'}, {'b': '2', 'a': '1'}),
        ({'a': [1, 2]}, MultiDict([('a', 1), ('a', 2)])),
        ({'a': b'x'}, {'a': bytearray(b'x')}),
    ],
)
def test_data_cache_keys_match_equivalent_bodies(data_1, data_2):
    assert create_key('POST', 'https://example.com', data=data_1) == create_key(
        'POST', 'https://example.com', data=data_2
    )


@pytest.mark.parametrize(
    'make_data',
    [
        lambda body: body,
        bytearray,
        lambda body: {'a': memoryview(body)},
    ],
    ids=['bytes', 'bytearray', 'multipart'],
)
def test_data_cache_keys_do_not_copy_body(make_data):
    data = make_data(bytes(BODY_SIZE))
    tracemalloc.start()
    try:
        create_key('POST', 'https://example.com', data=data)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < BODY_SIZE // 10


@pytest.mark.asyncio
@pytest.mark.filterwarnings('ignore:In v4, passing bytes:DeprecationWarning')
@pytest.mark.parametrize(
    'data_1, data_2',
    [
        ({'a': b'x'}, {'a': 'x'}),
        ({'a': [1, 2]}, {'a': '[1, 2]'}),
    ],
)
async def test_data_bodies_sent_differently_cache_separately(aiohttp_server, data_1, data_2):
    async def echo(request):
        body = '' if request.content_type.startswith('multipart/') else await request.text()
        return web.Response(text=f'{request.content_type} {body}')

    app = web.Application()
    app.router.add_post('/', echo)
    server = await aiohttp_server(app)
    async with CachedSession(cache=CacheBackend(allowed_methods=['POST'])) as session:
        response_1 = await session.post(server.make_url('/'), data=data_1)
        response_2 = await session.post(server.make_url('/'), data=data_2)
        assert not response_2.from_cache
        assert await response_1.text() != await response_2.text()
