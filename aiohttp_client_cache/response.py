from __future__ import annotations

import asyncio
from datetime import datetime
from logging import getLogger
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union, cast
from unittest.mock import Mock

from aiohttp import ClientResponse, ClientSession
from aiohttp.client_reqrep import RequestInfo
from aiohttp.helpers import BaseTimerContext
from aiohttp.streams import StreamReader
from aiohttp.tracing import Trace
from multidict import CIMultiDict, CIMultiDictProxy, MultiDict, MultiDictProxy
from yarl import URL

from aiohttp_client_cache.cache_control import utcnow

JsonResponse = Optional[Dict[str, Any]]
DictItems = List[Tuple[str, str]]
LinkItems = List[Tuple[str, DictItems]]
LinkMultiDict = MultiDictProxy[MultiDictProxy[Union[str, URL]]]

logger = getLogger(__name__)


class CachedResponse(ClientResponse):
    """A dataclass containing cached response information, used for serialization.
    It will mostly behave the same as a :py:class:`aiohttp.ClientResponse` that has been read,
    with some additional cache-related info.
    """

    def __init__(
        self,
        method: str,
        url: URL,
        *,
        writer: asyncio.Task[None],
        continue100: asyncio.Future[bool] | None,
        timer: BaseTimerContext,
        request_info: RequestInfo,
        traces: list[Trace],
        loop: asyncio.AbstractEventLoop,
        session: ClientSession,
    ) -> None:
        self._content: StreamReader | None = None
        self.created_at: datetime = utcnow()
        self.expires: datetime | None = None
        self.last_used: datetime = utcnow()
        self.from_cache = False
        super().__init__(
            method,
            url,
            writer=writer,
            continue100=continue100,
            timer=timer,
            request_info=request_info,
            traces=traces,
            loop=loop,
            session=session,
        )

    def __getstate__(self):
        state = self.__dict__.copy()
        for k in (
            '_request_info',
            '_headers',
            '_cache',
            '_loop',
            '_timer',
            '_resolve_charset',
            '_protocol',
            '_content',
        ):
            del state[k]
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._cache = {}
        self.from_cache = True
        self._content = None

        def decode_header(header):
            """Decode an individual (key, value) pair"""
            return (
                header[0].decode('utf-8', 'surrogateescape'),
                header[1].decode('utf-8', 'surrogateescape'),
            )

        self.headers = CIMultiDictProxy(CIMultiDict([decode_header(h) for h in self.raw_headers]))

    def get_encoding(self):
        return self._encoding

    @property  # type: ignore[override]
    def request_info(self) -> RequestInfo:
        return RequestInfo(
            url=self.url,
            method=self.method,
            headers=self.headers,
            real_url=self.url,
        )

    # NOTE: We redefine the same just to get rid of the `@reify' that protects against writing.
    @property  # type: ignore[override]
    def headers(self) -> CIMultiDictProxy[str]:
        return self._headers

    @headers.setter
    def headers(self, v) -> None:
        self._headers = v

    async def postprocess(self, expires: datetime | None = None) -> CachedResponse:
        """Read response content, and reset StreamReader on original response.

        This can be called only on an instance after `ClientSession._request()` returns `CachedResponse`
        because inside the `ClientSession._request()` headers are assigined at the very end (after `Response.start()`).
        """
        assert isinstance(expires, datetime) or expires is None, type(expires)

        if not self._released:
            await self.read()

        self.content = CachedStreamReader(self._body)

        self.expires = expires

        if self.history:
            self._history = (*[await cast(CachedResponse, r).postprocess() for r in self.history],)

        # We must call `get_encoding` before pickling because pickling `_resolve_charset` raises
        # _pickle.PicklingError: Can't pickle <function ClientSession.<lambda> at 0x7f94fdd13c40>:
        # attribute lookup ClientSession.<lambda> on aiohttp.client failed
        self._encoding: str = super().get_encoding()

        return self

    @property
    def content(self) -> StreamReader:
        if self._content is None:
            self._content = CachedStreamReader(self._body)
        return self._content

    @content.setter
    def content(self, value: StreamReader):
        self._content = value

    @property
    def is_expired(self) -> bool:
        """Determine if this cached response is expired"""
        try:
            return self.expires is not None and utcnow() > self.expires
        except (AttributeError, TypeError, ValueError):
            # Consider it expired and fetch a new response
            return True

    def reset(self):
        """Reset the stream reader to re-read a streamed response"""
        self._content = None


class CachedStreamReader(StreamReader):
    """A StreamReader loaded from previously consumed response content. This feeds cached data into
    the stream so it can support all the same behavior as the original stream: async iteration,
    chunked reads, etc.
    """

    def __init__(self, body: bytes | None = None):
        body = body or b''
        protocol = Mock(_reading_paused=False)
        super().__init__(protocol, limit=len(body), loop=None)
        self.feed_data(body)
        self.feed_eof()


def _to_str_tuples(data: Mapping) -> DictItems:
    return [(k, str(v)) for k, v in data.items()]


def _to_url_multidict(data: DictItems) -> MultiDict:
    return MultiDict([(k, URL(url)) for k, url in data])
