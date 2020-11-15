# aiohttp-client-cache
See full documentation at https://aiohttp-client-cache.readthedocs.io

[![Build status](https://github.com/JWCook/aiohttp-client-cache/workflows/Build/badge.svg)](https://github.com/JWCook/aiohttp-client-cache/actions)
[![Documentation Status](https://img.shields.io/readthedocs/aiohttp-client-cache/stable?label=docs)](https://aiohttp-client-cache.readthedocs.io/en/latest/)
[![PyPI](https://img.shields.io/pypi/v/aiohttp-client-cache?color=blue)](https://pypi.org/project/aiohttp-client-cache)
[![PyPI - Python Versions](https://img.shields.io/pypi/pyversions/aiohttp-client-cache)](https://pypi.org/project/aiohttp-client-cache)
[![PyPI - Format](https://img.shields.io/pypi/format/aiohttp-client-cache?color=blue)](https://pypi.org/project/aiohttp-client-cache)

<!--- [![Coverage Status](https://coveralls.io/repos/github/JWCook/aiohttp-client-cache/badge.svg?branch=master)](https://coveralls.io/github/JWCook/aiohttp-client-cache?branch=master) --->

`aiohttp-client-cache` is an async persistent cache for [aiohttp](https://docs.aiohttp.org) 
requests, based on [requests-cache](https://github.com/reclosedev/requests-cache).

Not to be confused with [aiohttp-cache](https://github.com/cr0hn/aiohttp-cache), which is a cache
for the aiohttp web server. This package is, as you might guess, specifically for the aiohttp client.

**This is an early work in progress and not yet fully functional!**

## Installation
Requires python 3.7+

Install the latest stable version with pip:
```bash
pip install aiohttp-client-cache
```

To set up for local development:

```bash
$ git clone https://github.com/JWCook/aiohttp-client-cache
$ cd aiohttp-client-cache
$ pip install -Ue ".[dev]"
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
