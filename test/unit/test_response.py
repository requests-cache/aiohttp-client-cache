import pytest

from aiohttp import ClientResponseError, ClientSession, web

from aiohttp_client_cache.response import CachedResponse, RequestInfo


async def get_real_response():
    async with ClientSession() as session:
        return await session.get('http://httpbin.org/get')


async def get_test_response(client_factory, url='/'):
    app = web.Application()
    client = await client_factory(app)
    client_response = await client.get(url)
    return await CachedResponse.from_client_response(client_response)


async def test_response__basic_attrs(aiohttp_client):
    response = await get_test_response(aiohttp_client)

    assert response.method == 'GET'
    assert response.reason == 'Not Found'
    assert response.status == 404
    assert response.encoding == 'utf-8'
    assert response.headers['Content-Type'] == 'text/plain; charset=utf-8'
    assert await response.text() == '404: Not Found'
    assert response.history == tuple()
    assert response.is_expired is False


async def test_response__encoding(aiohttp_client):
    response = await get_test_response(aiohttp_client)
    assert response.encoding == response.get_encoding() == 'utf-8'


async def test_response__request_info(aiohttp_client):
    response = await get_test_response(aiohttp_client)
    request_info = response.request_info

    assert isinstance(request_info, RequestInfo)
    assert request_info.method == 'GET'
    assert request_info.url and request_info.real_url
    assert 'Host' in request_info.headers and 'User-Agent' in request_info.headers


# TODO
async def test_response__history(aiohttp_client):
    pass


# TODO
async def test_response__json(aiohttp_client):
    pass


# TODO
async def test_response__raise_for_status__200(aiohttp_client):
    pass
    # response = await get_test_response(aiohttp_client, '/valid_url')
    # assert not response.raise_for_status()
    # assert response.ok is True


# TODO
async def test_response__raise_for_status__404(aiohttp_client):
    response = await get_test_response(aiohttp_client, '/valid_url')
    with pytest.raises(ClientResponseError):
        response.raise_for_status()
    assert response.ok is False


async def test_response__text(aiohttp_client):
    response = await get_test_response(aiohttp_client)
    assert await response.text() == '404: Not Found'


async def test_response__no_op(aiohttp_client):
    # Just make sure CachedResponse doesn't explode if extra functions from ClientSession are called
    response = await get_test_response(aiohttp_client)
    response.read()
    response.release()
