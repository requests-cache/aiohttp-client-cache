# aiohttp-client-cache
`aiohttp-client-cache` is an async persistent cache for [aiohttp](https://docs.aiohttp.org) 
requests, based on [requests-cache](https://github.com/reclosedev/requests-cache).
Not to be confused with [aiohttp-cache](https://github.com/cr0hn/aiohttp-cache), which is a cache
for the aiohttp web server. This package is, as you might guess, specifically for the aiohttp client.

**This is an early work in progress and not yet fully functional!**

## Installation
Requires python 3.7+

**WIP; package not yet on pypi**
```python
pip install aiohttp-client-cache
```

## Usage example
```python
from aiohttp_client_cache import CachedSession
session = CachedSession('demo_cache', backend='sqlite')
response = await session.get('http://httpbin.org/get')
```

Afterward, all responses with headers and cookies will be transparently cached to
a database named `demo_cache.sqlite`. For example, following code will take only
1-2 seconds instead of 10, and will run instantly on next launch:

```python
for i in range(10):
    await session.get('http://httpbin.org/delay/1')
```

**Note:** `aiohttp-client-cache` ignores all cache headers, it just caches the data for the time you specify.
If you need library that uses HTTP headers and status codes, take a look at
[CacheControl](https://github.com/ionrock/cachecontrol).

## Cache Backends
Several backends are available:

* `sqlite`: SQLite database (**default**)
* `redis`: Stores all data in a redis cache (requires [redis-py](https://github.com/andymccurdy/redis-py))
* `mongodb`: MongoDB database (requires [pymongo](https://pymongo.readthedocs.io/en/stable/)))
    * `gridfs`: MongoDB GridFS enables storage of documents greater than 16MB
* `memory`: Not persistent, simply stores all data in Python ``dict`` in memory

You can also provide your own backend by subclassing `aiohttp_client_cache.backends.BaseCache`.

## Expiration
If you are using the `expire_after` parameter , responses are removed from the storage the next time
the same request is made. If you want to manually purge all expired items, you can use
`CachedSession.delete_expired_responses`. Example:

```python
session = CachedSession(expire_after=1)
await session.remove_expired_responses()
```
