# TODO: CachedResponse may be better as a non-slotted subclass of ClientResponse.
#     Will look into this when working on issue #67.
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from functools import singledispatch
from http.cookies import SimpleCookie
from logging import getLogger
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union
from unittest.mock import Mock

import attr
from aiohttp import ClientResponse, ClientResponseError, hdrs, multipart
from aiohttp.client_reqrep import ContentDisposition, MappingProxyType, RequestInfo
from aiohttp.helpers import HeadersMixin
from aiohttp.streams import StreamReader
from aiohttp.typedefs import RawHeaders, StrOrURL
from multidict import CIMultiDict, CIMultiDictProxy, MultiDict, MultiDictProxy
from yarl import URL

from aiohttp_client_cache.cache_control import utcnow

# CachedResponse attributes to not copy directly from ClientResponse
EXCLUDE_ATTRS = {
    '_body',
    '_content',
    '_links',
    'created_at',
    'encoding',
    'expires',
    'history',
    'last_used',
    'real_url',
    'request_info',
}

# Default attributes to add to ClientResponse objects
CACHED_RESPONSE_DEFAULTS = {
    'created_at': None,
    'expires': None,
    'from_cache': False,
    'is_expired': False,
}

JsonResponse = Optional[Dict[str, Any]]
DictItems = List[Tuple[str, str]]
LinkItems = List[Tuple[str, DictItems]]
LinkMultiDict = MultiDictProxy[MultiDictProxy[Union[str, URL]]]

logger = getLogger(__name__)


@attr.s(slots=True)
class CachedResponse(HeadersMixin):
    """A dataclass containing cached response information, used for serialization.
    It will mostly behave the same as a :py:class:`aiohttp.ClientResponse` that has been read,
    with some additional cache-related info.
    """

    method: str = attr.ib()
    reason: str = attr.ib()
    status: int = attr.ib()
    url: URL = attr.ib(converter=URL)
    version: str = attr.ib()
    _body: Any = attr.ib(default=b'')
    _content: StreamReader | None = attr.ib(default=None)
    _links: LinkItems = attr.ib(factory=list)
    cookies: SimpleCookie = attr.ib(factory=SimpleCookie)
    created_at: datetime = attr.ib(factory=utcnow)
    encoding: str = attr.ib(default='utf-8')
    expires: datetime | None = attr.ib(default=None)
    raw_headers: RawHeaders = attr.ib(factory=tuple)
    real_url: StrOrURL = attr.ib(default=None)
    history: tuple = attr.ib(factory=tuple)
    last_used: datetime = attr.ib(factory=utcnow)

    @classmethod
    async def from_client_response(
        cls, client_response: ClientResponse, expires: datetime | None = None
    ):
        """Convert a ClientResponse into a CachedReponse"""
        # Copy most attributes over as is
        copy_attrs = set(attr.fields_dict(cls).keys()) - EXCLUDE_ATTRS
        response = cls(**{k: getattr(client_response, k) for k in copy_attrs})

        # Read response content, and reset StreamReader on original response
        if not client_response._released:
            await client_response.read()
        response._body = client_response._body
        client_response.content = CachedStreamReader(client_response._body)

        # Set remaining attributes individually
        response.expires = expires
        response.links = client_response.links
        response.real_url = client_response.request_info.real_url

        # The encoding may be unset even if the response has been read, and
        # get_encoding() does not handle certain edge cases like an empty response body
        try:
            response.encoding = client_response.get_encoding()
        except (RuntimeError, TypeError):
            pass

        if client_response.history:
            response.history = (
                *[await cls.from_client_response(r) for r in client_response.history],
            )
        return response

    @property
    def content(self) -> StreamReader:
        if self._content is None:
            self._content = CachedStreamReader(self._body)
        return self._content

    @content.setter
    def content(self, value: StreamReader):
        self._content = value

    @property
    def content_disposition(self) -> ContentDisposition | None:
        """Get Content-Disposition headers, if any"""
        raw = self.headers.get(hdrs.CONTENT_DISPOSITION)
        if raw is None:
            return None
        disposition_type, params_dct = multipart.parse_content_disposition(raw)
        params = MappingProxyType(params_dct)
        filename = multipart.content_disposition_filename(params)
        return ContentDisposition(disposition_type, params, filename)

    @property
    def from_cache(self):
        return True

    @property
    def _headers(self) -> CIMultiDictProxy[str]:  # type: ignore[override]
        return self.headers

    @property
    def headers(self) -> CIMultiDictProxy[str]:
        """Get headers as an immutable, case-insensitive multidict from raw headers"""

        def decode_header(header):
            """Decode an individual (key, value) pair"""
            return (
                header[0].decode('utf-8', 'surrogateescape'),
                header[1].decode('utf-8', 'surrogateescape'),
            )

        return CIMultiDictProxy(CIMultiDict([decode_header(h) for h in self.raw_headers]))

    @property
    def host(self) -> str:
        return self.url.host or ''

    @property
    def is_expired(self) -> bool:
        """Determine if this cached response is expired"""
        try:
            return self.expires is not None and utcnow() > self.expires
        except (AttributeError, TypeError, ValueError):
            # Consider it expired and fetch a new response
            return True

    @property
    def links(self) -> MultiDictProxy:
        """Convert stored links into the format returned by :attr:`ClientResponse.links`"""
        items = [(k, _to_url_multidict(v)) for k, v in self._links]
        return MultiDictProxy(MultiDict([(k, MultiDictProxy(v)) for k, v in items]))

    @links.setter
    def links(self, value: Mapping):
        self._links = [(k, _to_str_tuples(v)) for k, v in value.items()]

    @property
    def ok(self) -> bool:
        """Returns ``True`` if ``status`` is less than ``400``, ``False`` if not"""
        return self.status < 400

    @property
    def request_info(self) -> RequestInfo:
        return RequestInfo(
            url=URL(self.url),
            method=self.method,
            headers=self.headers,
            real_url=URL(str(self.real_url)),
        )

    def get_encoding(self):
        return self.encoding

    async def json(self, encoding: str | None = None, **kwargs) -> dict[str, Any] | None:
        """Read and decode JSON response"""
        stripped = self._body.strip()
        if not stripped:
            return None
        return json.loads(stripped.decode(encoding or self.encoding))

    def raise_for_status(self):
        if self.status >= 400:
            raise ClientResponseError(
                self.request_info,
                self.history,
                status=self.status,
                message=self.reason,
                headers=self.headers,
            )

    async def read(self) -> bytes:
        """Read response payload."""
        return await self.content.read()

    def reset(self):
        """Reset the stream reader to re-read a streamed response"""
        self._content = None

    async def text(self, encoding: str | None = None, errors: str = 'strict') -> str:
        """Read response payload and decode"""
        return self._body.decode(encoding or self.encoding, errors=errors)

    # No-op/placeholder properties and methods that don't apply to a CachedResponse, but provide
    # compatibility with aiohttp.ClientResponse
    # ----------

    @property
    def _released(self):
        return True

    @property
    def connection(self):
        return None

    async def __aenter__(self) -> CachedResponse:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        pass

    @property
    def closed(self) -> bool:
        return True

    def close(self):
        pass

    async def wait_for_close(self):
        pass

    def release(self):
        pass

    async def start(self):
        pass

    async def terminate(self):
        pass


class CachedStreamReader(StreamReader):
    """A StreamReader loaded from previously consumed response content. This feeds cached data into
    the stream so it can support all the same behavior as the original stream: async iteration,
    chunked reads, etc.
    """

    def __init__(self, body: bytes | None = None):
        body = body or b''
        protocol = Mock(_reading_paused=False)
        super().__init__(protocol, limit=len(body), loop=asyncio.get_event_loop())
        self.feed_data(body)
        self.feed_eof()


AnyResponse = Union[ClientResponse, CachedResponse]


@singledispatch
def set_response_defaults(response):
    raise NotImplementedError


@set_response_defaults.register
def _(response: CachedResponse) -> CachedResponse:
    return response


@set_response_defaults.register
def _(response: ClientResponse) -> ClientResponse:
    """Set some default CachedResponse values on a ClientResponse object, so they can be
    expected to always be present
    """
    for k, v in CACHED_RESPONSE_DEFAULTS.items():
        setattr(response, k, v)
    return response


def _to_str_tuples(data: Mapping) -> DictItems:
    return [(k, str(v)) for k, v in data.items()]


def _to_url_multidict(data: DictItems) -> MultiDict:
    return MultiDict([(k, URL(url)) for k, url in data])
