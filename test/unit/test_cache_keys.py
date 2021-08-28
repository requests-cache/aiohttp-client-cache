import pytest

from aiohttp_client_cache.cache_keys import create_key

CACHE_KEY = '3da7c84fefc3f40e3223de763c16d5804e50f5b4b2bc8ff3f033e99c4640ac1b'


# All of the following variations should produce the same cache key
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
    assert create_key('GET', url, params=params) == CACHE_KEY
