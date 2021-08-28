"""The cache_keys module is mostly covered indirectly via other tests.
This just contains tests for some extra edge cases not covered elsewhere.
"""
import pytest

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
    ],
)
def test_normalize_url_params(url, params):
    """All of these variations should produce the same cache key"""
    cache_key = '247bdad30a3ccdcafc39a8bd2712ec79789d7b8aafce330a19dc0ddd680e9477'
    assert create_key('GET', url, params=params) == cache_key


@pytest.mark.parametrize('field', ['data', 'json'])
@pytest.mark.parametrize('body', [{'foo': 'bar'}, '{"foo": "bar"}', b'{"foo": "bar"}'])
def test_encode_request_body(body, field):
    """Request body should be handled correctly whether it's a dict or already serialized"""
    cache_key = create_key('GET', 'https://example.com', **{field: body})
    assert isinstance(cache_key, str)
