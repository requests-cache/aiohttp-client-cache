# aiohttp-client-cache

`aiohttp-client-cache` is (or rather, will be) an async persistent cache for the
[aiohttp](https://docs.aiohttp.org) client, ~~hastily hacked together~~ adapted from
[requests-cache](https://github.com/reclosedev/requests-cache).
Not to be confused with [aiohttp-cache](https://github.com/cr0hn/aiohttp-cache), which is a cache
for the server side.

**This is WIP and not yet functional!**


## Usage example

```python
from aiohttp_client_cache import CachedSession
session = CachedSession('demo_cache', backend='sqlite')
response = await session.get('http://httpbin.org/get')
```

Afterward, all responses with headers and cookies will be transparently cached to
`demo_cache.sqlite` database. For example, following code will take only
1-2 seconds instead of 10, and will run instantly on next launch:

```python
for i in range(10):
    await session.get('http://httpbin.org/delay/1')
```

## Note

`aiohttp-client-cache` ignores all cache headers, it just caches the data for the time you specify.
If you need library that uses HTTP headers and status codes, take a look at
[CacheControl](https://github.com/ionrock/cachecontrol).
