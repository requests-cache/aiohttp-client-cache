# aiohttp-client-cache

[![Build status](https://github.com/requests-cache/aiohttp-client-cache/actions/workflows/build.yml/badge.svg?branch=main)](https://github.com/requests-cache/aiohttp-client-cache/actions)
[![Documentation Status](https://img.shields.io/readthedocs/aiohttp-client-cache/latest?label=docs)](https://aiohttp-client-cache.readthedocs.io/en/stable/)
[![Codecov](https://codecov.io/gh/requests-cache/aiohttp-client-cache/branch/main/graph/badge.svg?token=I6PNLYTILM)](https://codecov.io/gh/requests-cache/aiohttp-client-cache)
[![PyPI](https://img.shields.io/pypi/v/aiohttp-client-cache?color=blue)](https://pypi.org/project/aiohttp-client-cache)
[![Conda](https://img.shields.io/conda/vn/conda-forge/aiohttp-client-cache?color=blue)](https://anaconda.org/conda-forge/aiohttp-client-cache)
[![PyPI - Python Versions](https://img.shields.io/pypi/pyversions/aiohttp-client-cache)](https://pypi.org/project/aiohttp-client-cache)
[![PyPI - Format](https://img.shields.io/pypi/format/aiohttp-client-cache?color=blue)](https://pypi.org/project/aiohttp-client-cache)

**aiohttp-client-cache** is an async persistent cache for [aiohttp](https://docs.aiohttp.org)
client requests, based on [requests-cache](https://github.com/reclosedev/requests-cache).

# Features

- **Ease of use:** Use as a [drop-in replacement](https://aiohttp-client-cache.readthedocs.io/en/stable/user_guide.html)
  for `aiohttp.ClientSession`
- **Customization:** Works out of the box with little to no config, but with plenty of options
  available for customizing cache
  [expiration](https://aiohttp-client-cache.readthedocs.io/en/stable/user_guide.html#cache-expiration)
  and other [behavior](https://aiohttp-client-cache.readthedocs.io/en/stable/user_guide.html#cache-options)
- **Persistence:** Includes several [storage backends](https://aiohttp-client-cache.readthedocs.io/en/stable/backends.html):
  SQLite, DynamoDB, MongoDB, DragonflyDB and Redis.

# Quickstart

First, install with pip (python 3.8+ required):

```bash
pip install aiohttp-client-cache[all]
```

**Note:**
Adding `[all]` will install optional dependencies for all supported backends. When adding this
library to your application, you can include only the dependencies you actually need; see individual
backend docs and [pyproject.toml](https://github.com/requests-cache/aiohttp-client-cache/blob/main/pyproject.toml)
for details.

## Basic Usage

Next, use [aiohttp_client_cache.CachedSession](https://aiohttp-client-cache.readthedocs.io/en/stable/modules/aiohttp_client_cache.session.html#aiohttp_client_cache.session.CachedSession)
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
# fmt: off
from aiohttp_client_cache import SQLiteBackend

cache = SQLiteBackend(
    cache_name='~/.cache/aiohttp-requests.db',  # For SQLite, this will be used as the filename
    expire_after=60*60,                         # By default, cached responses expire in an hour
    urls_expire_after={'*.fillmurray.com': -1}, # Requests for any subdomain on this site will never expire
    allowed_codes=(200, 418),                   # Cache responses with these status codes
    allowed_methods=['GET', 'POST'],            # Cache requests with these HTTP methods
    include_headers=True,                       # Cache requests with different headers separately
    ignored_params=['auth_token'],              # Keep using the cached response even if this param changes
    timeout=2.5,                                # Connection timeout for SQLite backend
)
```

# More Info

To learn more, see:

- [User Guide](https://aiohttp-client-cache.readthedocs.io/en/stable/user_guide.html)
- [Cache Backends](https://aiohttp-client-cache.readthedocs.io/en/stable/backends.html)
- [API Reference](https://aiohttp-client-cache.readthedocs.io/en/stable/reference.html)
- [Examples](https://aiohttp-client-cache.readthedocs.io/en/stable/examples.html)

# Feedback

If there is a feature you want, if you've discovered a bug, or if you have other general feedback, please
[create an issue](https://github.com/requests-cache/aiohttp-client-cache/issues/new/choose) for it!
