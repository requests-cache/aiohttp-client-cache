"""The cache_keys module is mostly covered indirectly via other tests.
This just contains tests for some extra edge cases not covered elsewhere.
"""

from __future__ import annotations

from copy import copy
from decimal import Decimal
from json import dumps

import pytest
from multidict import MultiDict

from aiohttp_client_cache.cache_keys import create_key


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
    cache_key = 'e93c762132a09fb2398beafee0ed2e9f4240ad941e905581631b9ac9e70ab40e'
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
