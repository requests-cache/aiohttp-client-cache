import json
from datetime import datetime
from http.cookies import SimpleCookie
from typing import Any, Dict, Iterable, Optional, Tuple, Union

import attr
from aiohttp import ClientResponse, ClientResponseError
from aiohttp.client_reqrep import ContentDisposition
from aiohttp.typedefs import RawHeaders, StrOrURL
from multidict import CIMultiDictProxy, MultiDict

# CachedResponse attributes to not copy directly from ClientResponse
EXCLUDE_ATTRS = {
    '_body',
    'created_at',
    'encoding',
    'expires',
    'history',
    'is_expired',
    'last_used',
    'request_info',
}
JsonResponse = Optional[Dict[str, Any]]


@attr.s(auto_attribs=True, slots=True)
class RequestInfo:
    """A picklable version of aiohttp.client_reqrep.RequestInfo"""

    url: str
    method: str
    real_url: str
    raw_headers: RawHeaders

    @classmethod
    def from_object(cls, request_info):
        return cls(
            url=str(request_info.url),
            method=request_info.method,
            raw_headers=(request_info.raw_headers.items()),
            real_url=str(request_info.real_url),
        )

    @property
    def headers(self) -> CIMultiDictProxy:
        return decode_headers(self.raw_headers)


@attr.s(slots=True)
class CachedResponse:
    """A dataclass containing cached response information, used for serialization.
    It will mostly behave the same as a :py:class:`aiohttp.ClientResponse` that has been read,
    with some additional cache-related info.
    """

    method: str = attr.ib()
    reason: str = attr.ib()
    status: int = attr.ib()
    url: StrOrURL = attr.ib()
    version: str = attr.ib()
    _body: Any = attr.ib(default=None)
    content_disposition: ContentDisposition = attr.ib(default=None)
    cookies: SimpleCookie = attr.ib(default=None)
    created_at: datetime = attr.ib(factory=datetime.utcnow)
    encoding: str = attr.ib(default=None)
    expires: Optional[datetime] = attr.ib(default=None)
    raw_headers: RawHeaders = attr.ib(factory=tuple)
    history: Iterable = attr.ib(factory=tuple)
    last_used: datetime = attr.ib(factory=datetime.utcnow)
    request_info: RequestInfo = attr.ib(default=None)

    @classmethod
    async def from_client_response(cls, client_response: ClientResponse, expires: datetime = None):
        """Convert a ClientResponse into a CachedReponse"""
        # Response may not have been read yet, if fetched by something other than CachedSession
        if not client_response._released:
            await client_response.read()

        # Copy most attributes over as is
        copy_attrs = set(attr.fields_dict(cls).keys()) - EXCLUDE_ATTRS
        response = cls(**{k: getattr(client_response, k) for k in copy_attrs})

        # Set some remaining attributes individually
        response._body = client_response._body
        response.expires = expires

        # The encoding may be unset even if the response has been read
        try:
            response.encoding = client_response.get_encoding()
        except RuntimeError:
            pass

        response.request_info = RequestInfo.from_object(client_response.request_info)
        response.url = str(client_response.url)
        if client_response.history:
            response.history = (
                *[await cls.from_client_response(r) for r in client_response.history],
            )
        return response

    @property
    def ok(self) -> bool:
        """Returns ``True`` if ``status`` is less than ``400``, ``False`` if not"""
        try:
            self.raise_for_status()
            return True
        except ClientResponseError:
            return False

    def get_encoding(self):
        return self.encoding

    @property
    def headers(self) -> CIMultiDictProxy:
        return decode_headers(self.raw_headers)

    @property
    def is_expired(self) -> bool:
        """Determine if this cached response is expired"""
        return self.expires is not None and datetime.utcnow() > self.expires

    async def json(self, encoding: Optional[str] = None, **kwargs) -> Optional[Dict[str, Any]]:
        """Read and decode JSON response"""

        stripped = self._body.strip()
        if not stripped:
            return None
        return json.loads(stripped.decode(encoding or self.encoding))

    def raise_for_status(self) -> None:
        if self.status >= 400:
            raise ClientResponseError(
                self.request_info,  # type: ignore  # These types are interchangeable
                tuple(),
                status=self.status,
                message=self.reason,
                headers=self.headers,
            )

    def read(self):
        """No-op function for compatibility with ClientResponse"""

    def release(self):
        """No-op function for compatibility with ClientResponse"""

    async def text(self, encoding: Optional[str] = None, errors: str = "strict") -> str:
        """Read response payload and decode"""
        return self._body.decode(encoding or self.encoding, errors=errors)


def decode_headers(raw_headers: RawHeaders) -> CIMultiDictProxy:
    """Get an immutable, case-insensitive header dict from raw headers"""
    return CIMultiDictProxy(MultiDict([decode_header(h) for h in raw_headers]))


def decode_header(header: Tuple[bytes, bytes]) -> Tuple[str, str]:
    """Decode a raw header key-value pair"""
    return (
        header[0].decode('utf-8', 'surrogateescape'),
        header[1].decode('utf-8', 'surrogateescape'),
    )


AnyResponse = Union[ClientResponse, CachedResponse]
