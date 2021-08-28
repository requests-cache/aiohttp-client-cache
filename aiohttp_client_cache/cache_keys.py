"""Functions for creating keys used for cache requests"""
import hashlib
from collections.abc import Mapping
from typing import Any, Dict, Iterable, Tuple
from urllib.parse import parse_qsl, urlparse, urlunparse

from aiohttp import ClientRequest
from aiohttp.typedefs import StrOrURL
from url_normalize import url_normalize


def create_key(
    method: str,
    url: StrOrURL,
    params: Dict = None,
    data: Dict = None,
    json: Dict = None,
    headers: Dict = None,
    include_headers: bool = False,
    ignored_params: Iterable[str] = None,
    **kwargs,
) -> str:
    """Create a unique cache key based on request details"""
    norm_url, params = normalize_url_params(url, params)

    if ignored_params:
        params = filter_ignored_params(params, ignored_params)
        data = filter_ignored_params(data, ignored_params)
        json = filter_ignored_params(json, ignored_params)

    key = hashlib.sha256()
    key.update(method.upper().encode())
    key.update(norm_url.encode())
    key.update(encode_dict(params))
    key.update(encode_dict(data))
    key.update(encode_dict(json))

    if include_headers and headers is not None and headers != ClientRequest.DEFAULT_HEADERS:
        for name, value in sorted(headers.items()):
            key.update(name.encode())
            key.update(value.encode())
    return key.hexdigest()


def filter_ignored_params(data, ignored_params: Iterable[str]):
    """Remove any ignored params from an object, if it's dict-like"""
    if not isinstance(data, Mapping) or not ignored_params:
        return data
    return {k: v for k, v in data.items() if k not in ignored_params}


def normalize_url_params(url, params: Dict = None) -> Tuple[str, Dict]:
    """Strip off any request params manually added to URL and add to `params`"""
    params = params or {}
    url = url_normalize(str(url))
    tokens = urlparse(url)
    if tokens.query:
        query = parse_qsl(tokens.query)
        params.update(query)
        url = urlunparse(
            (tokens.scheme, tokens.netloc, tokens.path, tokens.params, '', tokens.fragment)
        )

    return url, params


def encode_dict(data: Any) -> bytes:
    if isinstance(data, bytes):
        return data
    elif not isinstance(data, Mapping):
        return str(data).encode()
    item_pairs = [f'{k}={v}' for k, v in sorted((data or {}).items())]
    return '&'.join(item_pairs).encode()
