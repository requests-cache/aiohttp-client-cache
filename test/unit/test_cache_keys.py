"""The cache_keys module is mostly covered indirectly via other tests.
This just contains tests for some extra edge cases not covered elsewhere.
"""

from __future__ import annotations

from copy import copy

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
    cache key distict from a request with only one of that parameter name.
    """
    assert (
        create_key('GET', url, params=params)
        != create_key('GET', 'http://url.com?param1=value1')
        != create_key('GET', 'http://url.com?param1=value2')
    )


@pytest.mark.parametrize('field', ['data', 'json'])
@pytest.mark.parametrize('body', [{'foo': 'bar'}, '{"foo": "bar"}', b'{"foo": "bar"}'])
def test_encode_request_body(body, field):
    """Request body should be handled correctly whether it's a dict or already serialized"""
    cache_key = create_key('GET', 'https://example.com', **{field: body})
    assert isinstance(cache_key, str)
