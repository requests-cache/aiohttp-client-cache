# User Guide

This section covers the main features of aiohttp-client-cache.

## Installation

Install with pip:

```bash
pip install aiohttp-client-cache
```

Or with conda, if you prefer:

```bash
conda install -c conda-forge aiohttp-client-cache
```

### Requirements

- Requires python 3.8+.
- You may need additional dependencies depending on which backend you want to use. To install with
  extra dependencies for all supported {ref}`backends`:
  ```bash
  pip install aiohttp-client-cache[all]
  ```

### Optional Setup Steps

- See {ref}`security` for recommended setup steps for more secure cache serialization.
- See {ref}`Contributing Guide <contributing:dev installation>` for setup steps for local development.

## General Usage

{py:class}`.CachedSession` can be used as a drop-in replacement for {py:class}`aiohttp.ClientSession`.
Basic usage looks like this:

```python
>>> from aiohttp_client_cache import CachedSession
>>>
>>> async with CachedSession() as session:
>>>     await session.get('http://httpbin.org/delay/1')
```

Any {py:class}`~aiohttp.ClientSession` method can be used (but see {ref}`user_guide:http methods` section
below for config details):

```python
>>> await session.request('GET', 'http://httpbin.org/get')
>>> await session.head('http://httpbin.org/get')
```

Caching can be temporarily disabled with {py:meth}`.CachedSession.disabled`:

```python
>>> async with session.disabled():
...     await session.get('http://httpbin.org/get')
```

The best way to clean up your cache is through {ref}`user_guide:cache expiration`, but you can also
clear out everything at once with {py:meth}`.CacheBackend.clear`:

```python
>>> await session.cache.clear()
```

## Cache Options

A number of options are available to modify which responses are cached and how they are cached.

### HTTP Methods

By default, only GET and HEAD requests are cached. To cache additional HTTP methods, specify them
with `allowed_methods`. For example, caching POST requests can be used to ensure you don't send
the same data multiple times:

```python
>>> cache = SQLiteBackend(allowed_methods=('GET', 'POST'))
>>> async with CachedSession(cache=cache) as session:
>>>     await session.post('http://httpbin.org/post', json={'param': 'value'})
```

### Status Codes

By default, only responses with a 200 status code are cached. To cache additional status codes,
specify them with `allowed_codes`"

```python
>>> cache = SQLiteBackend(allowed_codes=(200, 418))
>>> async with CachedSession(cache=cache) as session:
>>>     await session.get('http://httpbin.org/teapot')
```

### Request Parameters

By default, all request parameters are taken into account when caching responses. In some cases,
there may be request parameters that don't affect the response data, for example authentication tokens
or credentials. If you want to ignore specific parameters, specify them with `ignored_parameters`:

```python
>>> cache = SQLiteBackend(ignored_parameters=['auth-token'])
>>> async with CachedSession(cache=cache) as session:
>>>     # Only the first request will be sent
>>>     await session.get('http://httpbin.org/get', params={'auth-token': '2F63E5DF4F44'})
>>>     await session.get('http://httpbin.org/get', params={'auth-token': 'D9FAEB3449D3'})
```

### Request Headers

In some cases, different headers may result in different response data, so you may want to cache
them separately. To enable this, use `include_headers`:

```python
>>> cache = SQLiteBackend(include_headers=True)
>>> async with CachedSession(cache=cache) as session:
>>>     # Both of these requests will be sent and cached separately
>>>     await session.get('http://httpbin.org/headers', {'Accept': 'text/plain'})
>>>     await session.get('http://httpbin.org/headers', {'Accept': 'application/json'})
```

## Cache Expiration

By default, cached responses will be stored indefinitely. You can initialize the cache with an
`expire_after` value to specify how long responses will be cached.

### Expiration Values

`expire_after` can be any of the following:

- `-1`: Never expire
- `0` Expire immediately, e.g. skip writing to the cache
- A positive number (in seconds)
- A {py:class}`~datetime.timedelta`
- A {py:class}`~datetime.datetime`

Examples:

```python
>>> # Set expiration for the session using a value in seconds
>>> cache = SQLiteBackend(expire_after=360)

>>> # To specify a different unit of time, use a timedelta
>>> from datetime import timedelta
>>> cache = SQLiteBackend(expire_after=timedelta(days=30))

>>> # Update an existing session to disable expiration (i.e., store indefinitely)
>>> session.expire_after = -1
```

### URL Patterns

You can use `urls_expire_after` to set different expiration values for different requests, based on
URL glob patterns. This allows you to customize caching based on what you know about the resources
you're requesting. For example, you might request one resource that gets updated frequently, another
that changes infrequently, and another that never changes. Example:

```python
>>> cache = SQLiteBackend(
...     urls_expire_after={
...         '*.site_1.com': 30,
...         'site_2.com/resource_1': 60 * 2,
...         'site_2.com/resource_2': 60 * 60 * 24,
...         'site_2.com/static': -1,
...     }
... )
```

**Notes:**

- `urls_expire_after` should be a dict in the format `{'pattern': expire_after}`
- `expire_after` accepts the same types as `CacheBackend.expire_after`
- Patterns will match request **base URLs**, so the pattern `site.com/resource/` is equivalent to
  `http*://site.com/resource/**`
- If there is more than one match, the first match will be used in the order they are defined
- If no patterns match a request, `CacheBackend.expire_after` will be used as a default.

### Cache-Control

:::{warning}
This is **not** intended to be a thorough or strict implementation of header-based HTTP caching,
e.g. according to RFC 2616.
:::

Optional support is included for a simplified subset of
[Cache-Control](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control)
and other cache headers in both requests and responses. To enable this behavior, use the
`cache_control` backend option:

```python
>>> cache = SQLiteBackend(cache_control=True)
```

**Supported request headers:**

- `Cache-Control: max-age`: Used as the expiration time in seconds
- `Cache-Control: no-cache`: Skips reading response data from the cache
- `Cache-Control: no-store`: Skips reading and writing response data from/to the cache

**Supported response headers:**

- `Cache-Control: max-age`: Used as the expiration time in seconds
- `Cache-Control: no-store` Skips writing response data to the cache
- `Expires`: Used as an absolute expiration time

**Notes:**

- Unlike a browser or proxy cache, `max-age=0` does not currently clear previously cached responses.
- If enabled, Cache-Control directives will take priority over any other `expire_after` value.
  See {ref}`user_guide:expiration precedence` for the full order of precedence.

### Removing Expired Responses

For better performance, expired responses won't be removed immediately, but will be removed
(or replaced) the next time they are requested. To manually clear all expired responses, use
{py:meth}`.CachedSession.delete_expired_responses`:

```python
>>> session.delete_expired_responses()
```

You can also apply a different `expire_after` to previously cached responses, which will
revalidate the cache with the new expiration time:

```python
>>> session.delete_expired_responses(expire_after=timedelta(days=30))
```

### Expiration Precedence

Expiration can be set on a per-session, per-URL, or per-request basis, in addition to cache
headers. When there are multiple values provided for a given request, the following order of
precedence is used:

1. Cache-Control request headers (if enabled)
2. Cache-Control response headers (if enabled)
3. Per-request expiration (`expire_after` argument for {py:meth}`.CachedSession.request`)
4. Per-URL expiration (`urls_expire_after` argument for {py:class}`.CachedSession`)
5. Per-session expiration (`expire_after` argument for {py:class}`.CacheBackend`)

## Cache Inspection

Here are some ways to get additional information out of the cache session, backend, and responses:

### Response Attributes

The following attributes are available on both cached and new responses returned from {py:class}`.CachedSession`:

- `from_cache`: indicates if the response came from the cache
- `created_at`: {py:class}`~datetime.datetime` of when the cached response was created or last updated
- `expires`: {py:class}`~datetime.datetime` after which the cached response will expire
- `is_expired`: indicates if the cached response is expired (if an old response was returned due to a request error)

Examples:

```python
>>> from aiohttp_client_cache import CachedSession
>>> session = CachedSession(expire_after=timedelta(days=1))

>>> # Placeholders are added for non-cached responses
>>> r = await session.get('http://httpbin.org/get')
>>> print(r.from_cache, r.created_at, r.expires, r.is_expired)
False None None None

>>> # Values will be populated for cached responses
>>> r = await session.get('http://httpbin.org/get')
>>> print(r.from_cache, r.created_at, r.expires, r.is_expired)
True 2021-01-01 18:00:00 2021-01-02 18:00:00 False
```

### Cache Contents

You can use {py:meth}`.CachedSession.cache.get_urls` to see all URLs currently in the cache:

```python
>>> async for url in session.cache.get_urls():
...     print(url)
['https://httpbin.org/get', 'https://httpbin.org/stream/100']
```

If needed, you can get more details on cached responses via `CachedSession.cache.responses`, which
is a interface to the cache backend. See {py:class}`.CachedResponse` for a full list of
attributes available.

For example, if you wanted to to see all URLs requested with a specific method:

```python
>>> post_urls = [
>>>     response.url async for response in session.cache.responses.values()
>>>     if response.method == 'POST'
>>> ]
```

You can also inspect `CachedSession.cache.redirects`, which maps redirect URLs to keys of the
responses they redirect to.

## Other Cache Features

### Custom Response Filtering

If you need more advanced behavior for determining what to cache, you can provide a custom filtering
function via the `filter_fn` param. This can by any function or coroutine that takes a
{py:class}`aiohttp.ClientResponse` object and returns a boolean indicating whether or not that
response should be cached. It will be applied to both new responses (on write) and previously cached
responses (on read). Example:

```python
>>> from sys import getsizeof
>>> from aiohttp_client_cache import CachedSession, SQLiteCache
>>>
>>> async def filter_by_size(response):
>>>     """Don't cache responses with a body over 1 MB"""
>>>     return getsizeof(response._body) <= 1024 * 1024
>>>
>>> cache = SQLiteCache(filter_fn=filter_by_size)
```

### Library Compatibility

This library works by extending `aiohttp.ClientSession`, and there are other libraries out there
that do the same. For that reason a mixin class is included, so you can create a custom class with
behavior from multiple `aiohttp`-based libraries:

```python
>>> from aiohttp import ClientSession
>>> from aiohttp_client_cache import CacheMixin
>>> from some_other_library import CustomMixin
>>>
>>> class CustomSession(CacheMixin, CustomMixin, ClientSession):
...     """Session with features from both aiohttp_client_cache and some_other_library"""
```
