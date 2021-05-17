# aiohttp-client-cache

[![Build status](https://github.com/JWCook/aiohttp-client-cache/workflows/Build/badge.svg)](https://github.com/JWCook/aiohttp-client-cache/actions)
[![Documentation Status](https://img.shields.io/readthedocs/aiohttp-client-cache/stable?label=docs)](https://aiohttp-client-cache.readthedocs.io/en/latest/)
[![PyPI](https://img.shields.io/pypi/v/aiohttp-client-cache?color=blue)](https://pypi.org/project/aiohttp-client-cache)
[![PyPI - Python Versions](https://img.shields.io/pypi/pyversions/aiohttp-client-cache)](https://pypi.org/project/aiohttp-client-cache)
[![PyPI - Format](https://img.shields.io/pypi/format/aiohttp-client-cache?color=blue)](https://pypi.org/project/aiohttp-client-cache)
<!--- [![Coverage Status](https://coveralls.io/repos/github/JWCook/aiohttp-client-cache/badge.svg?branch=master)](https://coveralls.io/github/JWCook/aiohttp-client-cache?branch=master) --->

See full documentation at https://aiohttp-client-cache.readthedocs.io

**aiohttp-client-cache** is an async persistent cache for [aiohttp](https://docs.aiohttp.org)
requests, based on [requests-cache](https://github.com/reclosedev/requests-cache).

Not to be confused with [aiohttp-cache](https://github.com/cr0hn/aiohttp-cache), which is a cache
for the aiohttp web server. This package is, as you might guess, specifically for the **aiohttp client**.

## Development Status
**This is an early work in progress!**

The current state is a working drop-in replacement (or mixin) for `aiohttp.ClientSession`, with a
fully async SQLite backend.
Additional backends are provided, but cache operations are still synchronous, and have had minimal testing.

Breaking changes should be expected until a `1.0` release.

## Installation
Requires python 3.7+

Install the latest stable version with pip:
```bash
pip install aiohttp-client-cache
```

**Note:** You will need additional dependencies depending on which backend you want to use; See
[Cache Backends](#cache-backends) section below for details.
To install with extra dependencies for all supported backends:
```bash
pip install aiohttp-client-cache[backends]
```

To set up for local development:

```bash
$ git clone https://github.com/JWCook/aiohttp-client-cache
$ cd aiohttp-client-cache
$ pip install -Ue ".[dev]"
$ # Optional but recommended:
$ pre-commit install --config .github/pre-commit.yml
```

## Usage example
See the [examples](https://github.com/JWCook/aiohttp-client-cache/blob/master/examples)
folder for more detailed usage examples.

Here is a simple example using an endpoint that takes 1 second to fetch.
After the first request, subsequent requests to the same URL will return near-instantly; so,
fetching it 10 times will only take ~1 second instead of 10.
```python
from aiohttp_client_cache import CachedSession, SQLiteBackend

async with CachedSession(cache=SQLiteBackend()) as session:
    for i in range(10):
        await session.get('http://httpbin.org/delay/1')
```

`aiohttp-client-cache` can also be used as a mixin, if you happen have other mixin classes that you
want to combine with it:
```python
from aiohttp import ClientSession
from aiohttp_client_cache import CacheMixin

class CustomSession(CacheMixin, CustomMixin, ClientSession):
    pass
```

## Cache Backends
Several backends are available. If one isn't specified, a simple in-memory cache will be used.

* `SQLiteBackend`: Uses a [SQLite](https://www.sqlite.org) database
  (requires [aiosqlite](https://github.com/omnilib/aiosqlite))
* `DynamoDBBackend`: Uses a [Amazon DynamoDB](https://aws.amazon.com/dynamodb/) database
  (requires [boto3](https://github.com/boto/boto3))
* `RedisBackend`: Uses a [Redis](https://redis.io/) cache
  (requires [redis-py](https://github.com/andymccurdy/redis-py))
* `MongoDBBackend`: Uses a [MongoDB](https://www.mongodb.com/) database
  (requires [motor](https://motor.readthedocs.io))
    * `GridFSBackend`: Uses a [MongoDB GridFS](https://docs.mongodb.com/manual/core/gridfs/) database,
      which enables storage of documents greater than 16MB
      (requires [pymongo](https://pymongo.readthedocs.io/en/stable/))

You can also provide your own backend by subclassing `aiohttp_client_cache.backends.BaseCache`.

## Expiration
If you are using the `expire_after` parameter, expired responses are removed from the storage the
next time the same request is made. If you want to manually purge all expired items, you can use
`CachedSession.delete_expired_responses`. Example:

```python
session = CachedSession(expire_after=3)   # Cached responses expire after 3 hours
await session.remove_expired_responses()  # Remove any responses over 3 hours old
```

## Conditional Caching
Caching behavior can be customized by defining various conditions:
* Response status codes
* Request HTTP methods
* Request headers
* Specific request parameters
* Custom filter function

See [CacheBackend](https://aiohttp-client-cache.readthedocs.io/en/latest/modules/aiohttp_client_cache.backends.base.html#aiohttp_client_cache.backends.base.CacheBackend)
docs for details.

## Credits
Thanks to [Roman Haritonov](https://github.com/reclosedev) and
[contributors](https://github.com/reclosedev/requests-cache/blob/master/CONTRIBUTORS.rst)
for the original `requests-cache`!

This project is licensed under the MIT license, with the exception of
[storage backend code](https://github.com/reclosedev/requests-cache/tree/master/requests_cache/backends/storage)
adapted from `requests-cache`, which is licensed under the BSD license
([copy included](https://github.com/JWCook/aiohttp-client-cache/blob/master/requests_cache.md)).
