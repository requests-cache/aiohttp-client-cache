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

## Development Status
**This is an early work in progress and not yet fully functional!**

The current state is a mostly working drop-in replacement for `aiohttp.ClientSession`.
However, the cache operations are still synchronous, with minimal testing and likely lots of bugs.

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
$ # Optional but recommended:
$ pre-commit install --config .github/pre-commit.yml
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
Several backends are available.
The default backend is `sqlite`, if installed; otherwise it falls back to `memory`.

* `sqlite` : SQLite database (requires [aiosqlite](https://github.com/omnilib/aiosqlite))
* `redis` : Stores all data in a redis cache (requires [redis-py](https://github.com/andymccurdy/redis-py))
* `mongodb` : MongoDB database (requires [pymongo](https://pymongo.readthedocs.io/en/stable/))
    * `gridfs` : MongoDB GridFS enables storage of documents greater than 16MB (requires pymongo)
* `memory` : Not persistent, simply stores all data in memory

You can also provide your own backend by subclassing `aiohttp_client_cache.backends.BaseCache`.

## Expiration
If you are using the `expire_after` parameter , responses are removed from the storage the next time
the same request is made. If you want to manually purge all expired items, you can use
`CachedSession.delete_expired_responses`. Example:

```python
session = CachedSession(expire_after=1)
await session.remove_expired_responses()
```

## Credits
Thanks to [Roman Haritonov](https://github.com/reclosedev) and
[contributors](https://github.com/reclosedev/requests-cache/blob/master/CONTRIBUTORS.rst)
for the original `requests-cache`!

This project is licensed under the MIT license, with the exception of portions reused from requests-cache
(primarily its [storage backends](https://github.com/reclosedev/requests-cache/tree/master/requests_cache/backends/storage)),
which is licensed under the BSD license (copy included).
