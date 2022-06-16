"""Functions for creating keys used for cache requests"""
import hashlib
import json
from collections.abc import Mapping
from io import IOBase
from logging import getLogger
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

from aiohttp import FormData
from aiohttp.typedefs import StrOrURL
from multidict import MultiDict
from url_normalize import url_normalize
from yarl import URL

# Maximum JSON request body size that will be normalized & filtered
MAX_NORM_BODY_SIZE = 10 * 1024 * 1024

ParamList = Optional[Iterable[str]]
RequestBody = Union[FormData, IOBase, Iterable, Mapping, bytes, str]
RequestParams = Union[Mapping, Sequence, str]

logger = getLogger(__name__)


def create_key(
    method: str,
    url: StrOrURL,
    params: Optional[RequestParams] = None,
    data: Optional[RequestBody] = None,
    json: Optional[Dict] = None,
    headers: Optional[Dict] = None,
    match_headers: bool = False,
    ignored_params: Optional[Iterable[str]] = None,
    **kwargs,
) -> str:
    """Create a unique cache key based on request details"""
    # Normalize and filter all relevant pieces of request data
    norm_url = normalize_url(url, params, ignored_params)
    norm_headers = normalize_headers(headers, ignored_params, match_headers)
    body = normalize_body(data or json, headers, ignored_params)

    # Create a hash based on the normalized and filtered request
    key_parts = [method.upper(), str(norm_url), body, *norm_headers]
    key = hashlib.sha256()
    for part in key_parts:
        key.update(encode(part))
    return key.hexdigest()


def normalize_url(
    url: StrOrURL,
    params: Optional[RequestParams] = None,
    ignored_params: Optional[Iterable[str]] = None,
) -> URL:
    """Normalize and filter a URL. This includes request parameters, IDN domains, scheme, host,
    port, etc.
    """
    # Apply general URL normalization
    url = URL(url_normalize(str(url)))

    # Combine `params` argument with URL query string, if needed
    if params:
        norm_params = MultiDict(url.query)
        norm_params.extend(url.with_query(params).query)
        url = url.with_query(norm_params)

    # Filter and normalize request params
    filtered_params = filter_sort_dict(url.query, ignored_params)
    return url.with_query(filtered_params)


def normalize_headers(
    headers: Optional[Mapping] = None,
    ignored_params: Optional[ParamList] = None,
    match_headers: Union[ParamList, bool, None] = None,
) -> List[str]:
    """Get and normalize only the headers we should match against, as a list of ``k=v`` strings"""
    if not headers or not match_headers:
        return []
    elif match_headers is True:
        match_headers = set(headers.keys()) - set(ignored_params or [])
    return [
        f'{k.lower()}={v}'
        for k, v in filter_sort_dict(headers, included_params=match_headers).items()
    ]


# TODO: Normalize urlencoded data
# TODO: Normalize form data
def normalize_body(
    body: Optional[RequestBody] = None,
    headers: Optional[Mapping] = None,
    ignored_params: Optional[ParamList] = None,
) -> bytes:
    """Normalize and filter a request body if possible, depending on Content-Type"""
    content_type = (headers or {}).get('Content-Type')

    if not body:
        return b''
    elif isinstance(body, Mapping):
        return encode_dict(filter_sort_dict(body, ignored_params))
    elif isinstance(body, (str, bytes)):
        # Filter and sort params if possible
        if content_type == 'application/json':
            body = normalize_json_body(body, ignored_params)
        # elif content_type == 'application/x-www-form-urlencoded':
        #     body = normalize_params(original_body, ignored_parameters)
    elif not isinstance(body, FormData):
        body = FormData(body)
        # ...

    return encode(body)


def normalize_json_body(
    original_body: Union[bytes, str], ignored_params: ParamList
) -> Union[str, bytes]:
    """Normalize and filter a request body with serialized JSON data"""
    if len(original_body) <= 2 or len(original_body) > MAX_NORM_BODY_SIZE:
        return original_body

    try:
        body = json.loads(decode(original_body))
        body = filter_sort_json(body, ignored_params)
        return json.dumps(body)
    # If it's invalid JSON, then don't mess with it
    except (AttributeError, TypeError, ValueError):
        logger.debug('Invalid JSON body')
        return original_body


def decode(value, encoding='utf-8') -> str:
    """Decode a value from bytes, if hasn't already been.
    Note: ``PreparedRequest.body`` is always encoded in utf-8.
    """
    return value.decode(encoding) if isinstance(value, bytes) else value


def encode(value, encoding='utf-8') -> bytes:
    """Encode a value to bytes, if it hasn't already been"""
    return value if isinstance(value, bytes) else str(value).encode(encoding)


def encode_dict(data: Any) -> bytes:
    if not data:
        return b''
    if isinstance(data, bytes):
        return data
    elif not isinstance(data, Mapping):
        return str(data).encode()
    item_pairs = [f'{k}={v}' for k, v in filter_sort_dict(data).items()]
    return '&'.join(item_pairs).encode()


def filter_sort_json(data: Union[List, Mapping], ignored_parameters: ParamList):
    """Handle either a mapping or list as JSON root"""
    if isinstance(data, Mapping):
        return filter_sort_dict(data, ignored_parameters)
    else:
        return filter_sort_list(data, ignored_parameters)


def filter_sort_dict(
    data: Mapping[str, Any], ignored_params: ParamList = None, included_params: ParamList = None
) -> MultiDict[str]:
    data = data or {}
    ignored_params = set(ignored_params or [])
    included_params = set(included_params or [])
    return MultiDict(
        (
            (k, v)
            for k, v in sorted(data.items(), key=lambda x: x[0].lower())
            if k not in ignored_params or k in included_params
        )
    )


def filter_sort_list(
    data: List, ignored_params: ParamList = None, included_params: ParamList = None
) -> List:
    data = data or []
    ignored_params = set(ignored_params or [])
    included_params = set(included_params or [])
    return [
        k
        for k in sorted(data, key=lambda x: x.lower())
        if k not in ignored_params or k in included_params
    ]
