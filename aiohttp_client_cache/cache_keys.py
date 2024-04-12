"""Functions for creating keys used for cache requests"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any, Iterable, Sequence, Union

from aiohttp.typedefs import StrOrURL
from multidict import MultiDict
from url_normalize import url_normalize
from yarl import URL

RequestParams = Union[Mapping, Sequence, str]


def create_key(
    method: str,
    url: StrOrURL,
    params: RequestParams | None = None,
    data: dict | None = None,
    json: dict | None = None,
    headers: dict | None = None,
    include_headers: bool = False,
    ignored_params: Iterable[str] | None = None,
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
    key = hashlib.sha256()
    key.update(method.upper().encode())
    key.update(str(norm_url).encode())
    key.update(encode_dict(data))
    key.update(encode_dict(json))
    if include_headers:
        key.update(encode_dict(headers))
    return key.hexdigest()


def filter_ignored_params(data, ignored_params: Iterable[str]):
    """Remove any ignored params from an object, if it's dict-like"""
    if not isinstance(data, Mapping) or not ignored_params:
        return data
    return MultiDict(((k, v) for k, v in data.items() if k not in ignored_params))


def normalize_url_params(url: StrOrURL, params: RequestParams | None = None) -> URL:
    """Normalize any combination of request parameter formats that aiohttp accepts"""
    if isinstance(url, str):
        url = URL(url)

    # Handle `params` argument, and combine with URL query string if it exists
    if params:
        norm_params = MultiDict(url.query)
        norm_params.extend(url.with_query(params).query)
        url = url.with_query(norm_params)

    # Apply additional normalization and convert back to URL object
    return URL(url_normalize(str(url)))


def encode_dict(data: Any) -> bytes:
    if not data:
        return b''
    if isinstance(data, bytes):
        return data
    elif not isinstance(data, Mapping):
        return str(data).encode()
    item_pairs = [f'{k}={v}' for k, v in sorted((data or {}).items())]
    return '&'.join(item_pairs).encode()
