"""Integration tests for behavior of CachedSession, backend classes, and storage classes"""
import pickle
import pytest
from uuid import uuid4

from itsdangerous.exc import BadSignature
from itsdangerous.serializer import Serializer

from aiohttp_client_cache import CachedSession, SQLiteBackend
from test.conftest import HTTPBIN_METHODS, from_cache, get_tempfile_session, httpbin

pytestmark = [pytest.mark.asyncio]


@pytest.mark.parametrize('method', HTTPBIN_METHODS)
@pytest.mark.parametrize('field', ['params', 'data', 'json'])
async def test_all_methods(field, method, tempfile_session):
    """Test all relevant combinations of methods and data fields. Requests with different request
    params, data, or json should be cached under different keys.
    """
    url = httpbin(method.lower())
    for params in [{'param_1': 1}, {'param_1': 2}, {'param_2': 2}]:
        response_1 = await tempfile_session.request(method, url, **{field: params})
        response_2 = await tempfile_session.request(method, url, **{field: params})
        assert not from_cache(response_1) and from_cache(response_2)


# TODO: Fix ignored parameters for data, json
@pytest.mark.parametrize('method', HTTPBIN_METHODS)
@pytest.mark.parametrize('field', ['params', 'data', 'json'])
async def test_all_methods__ignore_parameters(field, method, tempfile_session):
    """Test all relevant combinations of methods and data fields. Requests with different request
    params, data, or json should not be cached under different keys based on an ignored param.
    """
    tempfile_session.cache.ignored_params = ['ignored']
    params_1 = {'ignored': 1, 'not ignored': 1}
    params_2 = {'ignored': 2, 'not ignored': 1}
    params_3 = {'ignored': 2, 'not ignored': 2}
    url = httpbin(method.lower())

    response_1 = await tempfile_session.request(method, url, **{field: params_1})
    response_2 = await tempfile_session.request(method, url, **{field: params_1})
    response_3 = await tempfile_session.request(method, url, **{field: params_2})
    await tempfile_session.request(method, url, params={'a': 'b'})
    response_4 = await tempfile_session.request(method, url, **{field: params_3})

    assert not from_cache(response_1) and from_cache(response_2)
    assert from_cache(response_3) and not from_cache(response_4)


@pytest.mark.parametrize('n_redirects', range(1, 5))
@pytest.mark.parametrize('endpoint', ['redirect', 'absolute-redirect', 'relative-redirect'])
async def test_redirects(endpoint, n_redirects, tempfile_session):
    """Test all types of redirect endpoints with different numbers of consecutive redirects"""
    await tempfile_session.get(httpbin(f'redirect/{n_redirects}'))
    await tempfile_session.get(httpbin('get'))

    assert await tempfile_session.cache.redirects.size() == n_redirects


async def test_serializer_pickle():
    """Without a secret key, plain pickle should be used"""
    session = CachedSession()
    assert session.cache.responses._serializer == pickle


async def test_serializer_itsdangerous():
    """With a secret key, itsdangerous should be used"""
    secret_key = str(uuid4())
    async with get_tempfile_session(secret_key=secret_key) as session:
        assert isinstance(session.cache.responses._serializer, Serializer)

        # Simple serialize/deserialize round trip
        await session.cache.responses.write('key', 'value')
        assert (await session.cache.responses.read('key')) == 'value'

        # Without the same signing key, the item shouldn't be considered safe to deserialize
        cache = SQLiteBackend(cache_name=session.cache.name, secret_key='a different key')
        session_2 = CachedSession(cache=cache)
        with pytest.raises(BadSignature):
            await session_2.cache.responses.read('key')
