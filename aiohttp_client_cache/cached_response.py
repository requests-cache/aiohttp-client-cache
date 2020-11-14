import json
from http.cookies import SimpleCookie
from typing import Mapping, Any, Optional, Dict, Iterable

import attr
from aiohttp import ClientResponse, ClientResponseError
from aiohttp.client_reqrep import ContentDisposition, RequestInfo
from aiohttp.typedefs import StrOrURL

# CachedResponse attributes to not copy directly from ClientResponse
EXCLUDE_ATTRS = {
    'encoding',
    'history',
    'is_expired',
}


@attr.s(slots=True)
class CachedResponse:
    """A dataclass containing cached response information. Will mostly behave the same as a
    :py:class:`aiohttp.ClientResponse` that has been read.
    """

    method: str = attr.ib()
    encoding: str = attr.ib()
    reason: str = attr.ib()
    request_info: RequestInfo = attr.ib()
    status: int = attr.ib()
    url: StrOrURL = attr.ib()
    version: str = attr.ib()
    _body: Any = attr.ib(default=None)
    content: Any = attr.ib(default=None)
    content_disposition: ContentDisposition = attr.ib(default=None)
    cookies: SimpleCookie[str] = attr.ib(default=None)
    history: Iterable = attr.ib(default=None)
    is_expired: bool = attr.ib(default=False)
    headers: Mapping = attr.ib(factory=dict)

    @classmethod
    async def from_client_response(cls, client_response: ClientResponse):
        # Response may not have been read yet, if fetched by something other than CachedSession
        await client_response.read()

        # Copy most attributes over as is
        copy_attrs = set(attr.fields_dict(cls).keys()) - EXCLUDE_ATTRS
        response = cls(**{k: getattr(client_response, k) for k in copy_attrs})

        # Set some remaining attributes individually
        response.encoding = client_response.get_encoding()
        # response._history =  # TODO
        return response

    # TODO: Separately cache and fetch each request from history; store keys referencing cached request history
    @property
    def history(self):
        return None

    @property
    def ok(self) -> bool:
        """Returns ``True`` if ``status`` is less than ``400``, ``False`` if not"""
        try:
            self.raise_for_status()
            return True
        except ClientResponseError:
            return False

    def raise_for_status(self) -> None:
        if self.status >= 400:
            raise ClientResponseError(
                self.request_info,
                tuple(),
                status=self.status,
                message=self.reason,
                headers=self.headers,
            )

    def get_encoding(self):
        return self.encoding

    async def text(self, encoding: Optional[str] = None, errors: str = "strict") -> str:
        """Read response payload and decode"""
        return self._body.decode(encoding or self.encoding, errors=errors)

    async def json(self, encoding: Optional[str] = None, **kwargs) -> Optional[Dict[str, Any]]:
        """Read and decode JSON response"""

        stripped = self._body.strip()
        if not stripped:
            return None
        return json.loads(stripped.decode(encoding or self.encoding))
