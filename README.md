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

# Features
* **Ease of use:** Use as a [drop-in replacement](https://aiohttp-client-cache.readthedocs.io/en/latest/user_guide.html)
  for `aiohttp.ClientSession`
* **Customization:** Works out of the box with little to no config, but with plenty of options
  available for customizing cache
  [expiration](https://aiohttp-client-cache.readthedocs.io/en/latest/user_guide.html#cache-expiration)
  and other [behavior](https://aiohttp-client-cache.readthedocs.io/en/latest/user_guide.html#cache-options)
* **Persistence:** Includes several [storage backends](https://aiohttp-client-cache.readthedocs.io/en/latest/backends.html):
  SQLite, DynamoDB, MongoDB, and Redis.
  
# Development Status
**This library is a work in progress!**

Breaking changes should be expected until a `1.0` release, so version pinning is recommended.

I am developing this while also maintaining [requests-cache](https://github.com/reclosedev/requests-cache),
and my goal is to eventually have a similar (but not identical) feature set between the two libraries.
If there is a feature you want, or if you've discovered a bug, of it you have other general feedback, please
[create an issue](https://github.com/JWCook/aiohttp-client-cache/issues/new/choose) for it!

# Quickstart
First, install with pip (python 3.7+ required):
```bash
pip install aiohttp-client-cache
```

## Basic Usage
Next, use [aiohttp_client_cache.CachedSession](https://aiohttp-client-cache.readthedocs.io/en/latest/modules/aiohttp_client_cache.session.html#aiohttp_client_cache.session.CachedSession)
in place of [aiohttp.ClientSession](https://docs.aiohttp.org/en/stable/client_reference.html#aiohttp.ClientSession).
To briefly demonstrate how to use it:                                      
                                                                                                       
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

## Configuration
Several options are available to customize caching behavior. This example demonstrates a few of them:

```python
from aiohttp_client_cache import SQLiteBackend

cache = SQLiteBackend(
    cache_name='~/.cache/aiohttp-requests.db',  # For SQLite, this will be used as the filename
    expire_after=60*60,                         # By default, cached responses expire in an hour
    urls_expire_after={'*.fillmurray.com': -1}, # Requests for any subdomain on this site will never expire
    allowed_codes=(200, 418),                   # Cache responses with these status codes
    allowed_methods=('GET', 'POST'),            # Cache requests with these HTTP methods
    include_headers=True,                       # Cache requests with different headers separately
    ignored_params=['auth_token'],              # Keep using the cached response even if this param changes
    timeout=2.5,                                # Connection timeout for SQLite backend 
)
```

# More Info
To learn more, see:
* [User Guide](https://aiohttp-client-cache.readthedocs.io/en/latest/user_guide.html)
* [Cache Backends](https://aiohttp-client-cache.readthedocs.io/en/latest/backends.html)
* [API Reference](https://aiohttp-client-cache.readthedocs.io/en/latest/reference.html)
* [Examples](https://aiohttp-client-cache.readthedocs.io/en/latest/examples.html)
