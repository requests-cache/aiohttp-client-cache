from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import cast
from unittest import mock

from aiohttp.client_reqrep import ContentDisposition
import pytest
from aiohttp import ClientResponseError, ContentTypeError
from yarl import URL

from aiohttp_client_cache.session import CachedSession
from aiohttp_client_cache.cache_control import utcnow
from aiohttp_client_cache.response import CachedResponse, RequestInfo
from test.conftest import httpbin


async def get_test_response(
    relative_url: str = '',
    expires: datetime | None = None,
    *,
    headers: Mapping[str, str] | None = None,
    json: dict | None = None,
) -> CachedResponse:
    async with CachedSession() as session:
        async with session.get(
            httpbin(relative_url), headers=headers, json=json
        ) as cached_response:
            await cast(CachedResponse, cached_response).postprocess(
                expires or utcnow() + timedelta(minutes=1)
            )
            return cast(CachedResponse, cached_response)


async def test_basic_attrs():
    response = await get_test_response()

    assert response.method == 'GET'
    assert response.reason == 'OK'
    assert response.status == 200
    assert isinstance(response.url, URL)
    assert response.get_encoding() == 'utf-8'
    assert response.headers['Content-Type'] == 'text/html; charset=utf-8'
    assert await response.text()
    assert response.history == ()
    assert response._released is True


@mock.patch('aiohttp_client_cache.response.utcnow')
async def test_is_expired(mock_utcnow):
    mock_utcnow.return_value = utcnow()
    expires = utcnow() + timedelta(seconds=0.02)

    response = await get_test_response(expires=expires)

    assert response.expires == expires
    assert response.is_expired is False

    mock_utcnow.return_value += timedelta(0.02)
    assert response.is_expired is True


async def test_is_expired__invalid():
    with pytest.raises(AssertionError):
        await get_test_response(expires='wrong_value')  # type: ignore[arg-type]


async def test_content_disposition():
    response = await get_test_response(
        # URL example: https://github.com/postmanlabs/httpbin/issues/240#issuecomment-122426318
        'response-headers'
        + '?Content-Type=text/plain;'
        + '%20charset=UTF-8'
        + '&Content-Disposition=attachment;'
        + '%20filename%3d%22img.jpg%22; name=test-param'
    )

    content_disposition = cast(ContentDisposition, response.content_disposition)
    assert content_disposition.filename == 'img.jpg'
    assert content_disposition.type == 'attachment'
    assert content_disposition.parameters.get('name') == 'test-param'


async def test_encoding():
    response = await get_test_response()
    assert response.get_encoding() == 'utf-8'


async def test_request_info():
    response = await get_test_response(
        'headers', headers={'Content-Type': 'text/html', 'Content-Length': '0'}
    )
    request_info = response.request_info

    assert isinstance(request_info, RequestInfo)
    assert request_info.method == 'GET'
    assert request_info.url == request_info.real_url
    assert str(request_info.url).endswith('/headers')
    assert 'Content-Type' in request_info.headers
    assert 'Content-Length' in request_info.headers


async def test_headers():
    response = await get_test_response()
    raw_headers = dict(response.raw_headers)

    assert b'Content-Type' in raw_headers and b'Content-Length' in raw_headers
    assert 'Content-Type' in response.headers and 'Content-Length' in response.headers
    assert response._headers == response.headers
    with pytest.raises(TypeError):
        response.headers['key'] = 'value'  # type: ignore[index]


async def test_headers__mixin_attributes():
    response = await get_test_response('encoding/utf8')
    assert response.charset == 'utf-8'
    assert response.content_length == 14239
    assert response.content_type == 'text/html'


# TODO
async def test_history(aiohttp_client):
    pass


async def test_json():
    response = await get_test_response('/json')
    assert (await response.json())['slideshow']['author'] == 'Yours Truly'


async def test_json__non_json_content():
    response = await get_test_response('/status/200')
    with pytest.raises(ContentTypeError):
        await response.json()


async def test_raise_for_status__200():
    response = await get_test_response()
    response.raise_for_status()
    assert response.ok is True


async def test_raise_for_status__404():
    response = await get_test_response('/status/404')
    with pytest.raises(ClientResponseError):
        response.raise_for_status()
    assert response.ok is False


async def test_text():
    response = await get_test_response('robots.txt')
    assert await response.text() == 'User-agent: *\nDisallow: /deny\n'


async def test_read():
    async with CachedSession() as session:
        async with session.get(httpbin('robots.txt')) as cached_response:
            await cast(CachedResponse, cached_response).postprocess(None)

            assert await cached_response.read() == b'User-agent: *\nDisallow: /deny\n'


async def test_no_ops():
    # Just make sure CachedResponse doesn't explode if extra ClientResponse methods are called
    response = await get_test_response()

    response.release()
    response.close()
    assert response.closed is True
    await response.wait_for_close()
    assert response.connection is None
    assert response._released is True
