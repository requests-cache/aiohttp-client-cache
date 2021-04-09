# aiohttp-client-cache

[![Build status](https://github.com/JWCook/aiohttp-client-cache/workflows/Build/badge.svg)](https://github.com/JWCook/aiohttp-client-cache/actions)
[![Documentation Status](https://img.shields.io/readthedocs/aiohttp-client-cache/stable?label=docs)](https://aiohttp-client-cache.readthedocs.io/en/latest/)
[![Coverage Status](https://img.shields.io/coveralls/github/JWCook/aiohttp-client-cache)](https://coveralls.io/github/JWCook/aiohttp-client-cache?branch=main)
[![PyPI](https://img.shields.io/pypi/v/aiohttp-client-cache?color=blue)](https://pypi.org/project/aiohttp-client-cache)
[![PyPI - Python Versions](https://img.shields.io/pypi/pyversions/aiohttp-client-cache)](https://pypi.org/project/aiohttp-client-cache)
[![PyPI - Format](https://img.shields.io/pypi/format/aiohttp-client-cache?color=blue)](https://pypi.org/project/aiohttp-client-cache)

**aiohttp-client-cache** is an async persistent cache for [aiohttp](https://docs.aiohttp.org)
client requests.

See full documentation at https://aiohttp-client-cache.readthedocs.io

## Features
* **Ease of use:** Use as a [drop-in replacement](https://aiohttp-client-cache.readthedocs.io/en/latest/user_guide.html)
  for `aiohttp.ClientSession`
* **Customization:** Works out of the box with zero config, but with plenty of options available
  for customizing cache
  [expiration](https://aiohttp-client-cache.readthedocs.io/en/latest/user_guide.html#cache-expiration)
  and other [behavior](https://aiohttp-client-cache.readthedocs.io/en/latest/user_guide.html#cache-options)
* **Persistence:** Includes several [storage backends](https://aiohttp-client-cache.readthedocs.io/en/latest/backends.html):
  SQLite, DynamoDB, MongoDB, and Redis.
  
## Development Status
**This is an early work in progress!**

Bugs are likely, and breaking changes should be expected until a `1.0` release, so version pinning
is recommended.

I am developing this while also maintaining [requests-cache](https://github.com/reclosedev/requests-cache),
and my eventual goal is to have a similar (but not identical) feature set between the two libraries.
If there is a specific feature you want that aiohttp-client-cache doesn't yet have, please create an
issue to request it!

# Quickstart
Requires python 3.7+

First, install with pip:
```bash
pip install aiohttp-client-cache
````

## Basic Usage
Next, use [aiohttp_client_cache.CachedSession](https://aiohttp-client-cache.readthedocs.io/en/latest/modules/aiohttp_client_cache.session.html#aiohttp_client_cache.session.CachedSession)
in place of [aiohttp.ClientSession](https://docs.aiohttp.org/en/stable/client_reference.html#aiohttp.ClientSession)
to send and cache requests. To quickly demonstrate how to use it:                                      
                                                                                                       
**Replace this:**
```python
from aiohttp import ClientSession

async with ClientSession() as session:
    await session.get('http://httpbin.org/delay/1')                                                          
```                                                                                                    
                                                                                                       
**With this:**           
```python
from aiohttp_client_cache import CachedSession, SQLiteBackend

async with CachedSession(cache=SQLiteBackend('demo_cache')) as session:
    await session.get('http://httpbin.org/delay/1')                                                          
```

The URL in this example adds a delay of 1 second, simulating a slow or rate-limited website.
With caching, the response will be fetched once, saved to `demo_cache.sqlite`, and subsequent          
requests will return the cached response near-instantly.

## Customized Caching
Several options are available to customize caching behavior. This example demostrates a few of them:
```python
import asyncio
from datetime import timedelta
from aiohttp_client_cache import CachedSession, SQLiteBackend

cache = SQLiteBackend(
    cache_name='~/.cache/aiohttp-requests.db',  # For SQLite, this will be used as the filename
    expire_after=60*60,                         # By default, cached responses expire in an hour
    urls_expire_after={
      'httpbin.org/image': timedelta(days=7),   # Requests for this base URL with expire in a week
      '*.fillmurray.com': -1,                   # Requests matching this pattern will never expire
    }, 
    ignored_params=['auth_token'],              # Ignore this param when caching responses
)

async with CachedSession(cache=cache) as session:
    urls = [
        'https://httpbin.org/get',              # Expires in an hour
        'https://httpbin.org/image/jpeg',       # Expires in a week
        'http://www.fillmurray.com/460/300',    # Never expires
    ]
    tasks = [asyncio.create_task(session.get(url)) for url in urls]
    responses = await asyncio.gather(*tasks)
```
See [CacheBackend](https://aiohttp-client-cache.readthedocs.io/en/latest/modules/aiohttp_client_cache.backends.base.html#aiohttp_client_cache.backends.base.CacheBackend)
documentation for more usage details.


## Cache Backends
Several backends are available. If one isn't specified, a non-persistent in-memory cache will be used.

* `SQLiteBackend`: Uses a [SQLite](https://www.sqlite.org) database
  (requires [aiosqlite](https://github.com/omnilib/aiosqlite))
* `RedisBackend`: Uses a [Redis](https://redis.io/) cache
  (requires [aioredis](https://github.com/aio-libs/aioredis-py))
* `MongoDBBackend`: Uses a [MongoDB](https://www.mongodb.com/) database
  (requires [motor](https://motor.readthedocs.io))
* `DynamoDBBackend`: Uses a [Amazon DynamoDB](https://aws.amazon.com/dynamodb/) database
  (requires [aioboto3](https://github.com/terrycain/aioboto3))


## Next Steps
To find out more, see:

* The [User Guide](https://aiohttp-client-cache.readthedocs.io/en/latest/user_guide.html) section
* The [API Reference](https://aiohttp-client-cache.readthedocs.io/en/latest/reference.html) section
* More examples in the [examples/](https://github.com/JWCook/aiohttp-client-cache/blob/main/examples)
  folder

## Related Projects
Other python cache projects you may want to check out:

* [aiohttp-cache](https://github.com/cr0hn/aiohttp-cache): A server-side async HTTP cache for the
  `aiohttp` web server
* [diskcache](https://github.com/grantjenks/python-diskcache): A general-purpose (not HTTP-specific)
  file-based cache built on SQLite
* [aiocache](https://github.com/aio-libs/aiocache): General-purpose (not HTTP-specific) async cache
  backends
* [requests-cache](https://github.com/reclosedev/requests-cache) An HTTP cache for the `requests` library
* [CacheControl](https://github.com/ionrock/cachecontrol): An HTTP cache for `requests` that caches
  according to uses HTTP headers and status codes

## Credits
Thanks to [Roman Haritonov](https://github.com/reclosedev) and
[contributors](https://github.com/reclosedev/requests-cache/blob/master/CONTRIBUTORS.md)
for the original `requests-cache`!

This project is licensed under the MIT license, with the exception of portions of
[storage backend code](https://github.com/reclosedev/requests-cache/tree/master/requests_cache/backends/storage)
adapted from `requests-cache`, which is licensed under the BSD license
([copy included](https://github.com/JWCook/aiohttp-client-cache/blob/main/requests_cache.md)).
