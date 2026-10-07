"""Functions for creating keys used for cache requests"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable, Mapping, Sequence
from io import IOBase
from json import dumps
from operator import itemgetter
from typing import Any
from urllib.parse import urlencode

from aiohttp.typedefs import StrOrURL
from multidict import MultiDict
from url_normalize import url_normalize
from yarl import URL

RequestParams = Mapping | Sequence | str


def create_key(
    method: str,
    url: StrOrURL,
    params: RequestParams | None = None,
    data: dict | None = None,
    json: dict | None = None,
    headers: dict | None = None,
    include_headers: bool = False,
    ignored_params: Iterable[str] | None = None,
    json_serialize: Callable[[Any], str | bytes] = dumps,
    **kwargs,
) -> str:
    """Create a unique cache key based on request details"""
    # Normalize and filter all relevant pieces of request data
    norm_url = normalize_url_params(url, params)
    if ignored_params:
        filtered_params = filter_ignored_params(norm_url.query, ignored_params)
        norm_url = norm_url.with_query(filtered_params)
        headers = filter_ignored_params(headers, ignored_params)
        data = filter_ignored_params(data, ignored_params)
        json = filter_ignored_params(json, ignored_params)

    # Create a hash based on the normalized and filtered request
    components = [
        method.upper().encode(),
        str(norm_url).encode(),
        *encode_data(data),
        encode_json(json, json_serialize),
    ]
    if include_headers:
        components.append(encode_dict(headers))

    return hash_parts(components).hex()


def hash_parts(parts: Iterable[bytes | memoryview]) -> bytes:
    key = hashlib.sha256()
    for part in parts:
        key.update(memoryview(part).nbytes.to_bytes(8, 'big'))
        key.update(part)
    return key.digest()


def filter_ignored_params(
    data,
    # Always a set internally, but keep the public utility parameter as-is to avoid breaking changes.
    ignored_params: Iterable[str],
):
    """Remove any ignored params from an object, if it's dict-like"""
    if not isinstance(data, Mapping) or not ignored_params:
        return data
    return MultiDict(((k, v) for k, v in data.items() if k not in ignored_params))


def normalize_url_params(url: StrOrURL, params: RequestParams | None = None) -> URL:
    """Normalize any combination of request parameter formats that aiohttp accepts"""
    if isinstance(url, str):
        url = URL(url)

    # Handle trailing empty param
    norm_params = MultiDict([i for i in url.query.items() if i != ('', '')])

    # Combine `params` argument with URL query string if needed
    if params:
        norm_params.extend(url.with_query(params).query)

    # Sort params, apply additional normalization, and convert back to URL object
    url = url.with_query(sorted(norm_params.items()))
    return URL(url_normalize(str(url)))


def encode_data(data: Any) -> tuple[bytes, bytes | memoryview]:
    if data is None:
        return b'', b''
    if isinstance(data, (bytes, bytearray, memoryview)):
        return b'bytes', memoryview(data)
    if isinstance(data, str):
        return b'str', data.encode()
    if isinstance(data, Mapping):
        fields = sorted(data.items(), key=itemgetter(0))
        if any(isinstance(value, (bytes, bytearray, memoryview, IOBase)) for _, value in fields):
            return b'multipart', hash_parts(
                part for name, value in fields for part in (str(name).encode(), *encode_data(value))
            )
        return b'form', urlencode(fields, doseq=True).encode()
    return b'other', str(data).encode()


def encode_dict(data: Any) -> bytes:
    if not data:
        return b''
    if isinstance(data, bytes):
        return data
    elif not isinstance(data, Mapping):
        return str(data).encode()
    return urlencode(sorted(data.items())).encode()


def encode_json(data: Any, serializer: Callable[[Any], str | bytes] = dumps) -> bytes:
    if data is None:
        return b''
    if isinstance(data, Mapping):
        data = dict(data)
        if all(isinstance(key, str) for key in data):
            data = dict(sorted(data.items()))
    serialized = serializer(data)
    return serialized.encode() if isinstance(serialized, str) else serialized
