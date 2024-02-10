(backends)=

# Cache Backends

## Backend Classes

Several cache backends are included, which can be selected using the `cache` parameter for
{py:class}`.CachedSession`:

```{eval-rst}
.. autosummary::
    :nosignatures:

    aiohttp_client_cache.backends.base.CacheBackend
    aiohttp_client_cache.backends.dynamodb.DynamoDBBackend
    aiohttp_client_cache.backends.filesystem.FileBackend
    aiohttp_client_cache.backends.mongodb.MongoDBBackend
    aiohttp_client_cache.backends.redis.RedisBackend
    aiohttp_client_cache.backends.sqlite.SQLiteBackend
```

Usage example:

```python
>>> from aiohttp_client_cache import CachedSession, RedisBackend
>>>
>>> async with CachedSession(cache=RedisBackend()) as session:
...      await session.get('http://httpbin.org/get')
```

See {ref}`api-reference` for backend-specific usage details.

## Backend Cache Name

The `cache_name` parameter will be used as follows depending on the backend:

- DynamoDb: Table name
- Filesystem: Cache directory
- MongoDb: Database name
- Redis: Namespace, meaning all keys will be prefixed with `'<cache_name>:'`
- SQLite: Database path; user paths are allowed, e.g `~/.cache/my_cache.sqlite`

## Backend-Specific Arguments

When initializing a {py:class}`.CacheBackend`, you can provide any valid keyword arguments for the
backend's internal connection class or function.

For example, with {py:class}`.SQLiteBackend`, you can pass arguments accepted by
{py:func}`sqlite3.connect`:

```python
>>> cache = SQLiteBackend(
...     timeout=2.5,
...     uri='file://home/user/.cache/aiohttp-cache.db?mode=ro&cache=private',
... )
```

## Custom Backends

If the built-in backends don't suit your needs, you can create your own by making subclasses of
{py:class}`.CacheBackend` and {py:class}`.BaseCache`:

```python
>>> from aiohttp_client_cache import CachedSession
>>> from aiohttp_client_cache.backends import BaseCache, BaseStorage

>>> class CustomCache(BaseCache):
...     """Wrapper for higher-level cache operations. In most cases, the only thing you need
...     to specify here is which storage class(es) to use.
...     """
...     def __init__(self, **kwargs):
...         super().__init__(**kwargs)
...         self.redirects = CustomStorage(**kwargs)
...         self.responses = CustomStorage(**kwargs)

>>> class CustomStorage(BaseStorage):
...     """interface for lower-level backend storage operations"""
...     def __init__(self, **kwargs):
...         super().__init__(**kwargs)
...
...     async def contains(self, key: str) -> bool:
...         """Check if a key is stored in the cache"""
...
...     async def clear(self):
...         """Delete all items from the cache"""
...
...     async def delete(self, key: str):
...         """Delete an item from the cache"""
...
...     async def keys(self) -> AsyncIterable[str]:
...         """Get all keys stored in the cache"""
...
...     async def read(self, key: str) -> ResponseOrKey:
...         """Read anitem from the cache"""
...
...     async def size(self) -> int:
...         """Get the number of items in the cache"""
...
...     def values(self) -> AsyncIterable[ResponseOrKey]:
...         """Get all values stored in the cache"""
...
...     async def write(self, key: str, item: ResponseOrKey):
...         """Write an item to the cache"""
```

You can then use your custom backend in a {py:class}`.CachedSession` with the `cache` parameter:

```python
>>> session = CachedSession(cache=CustomCache())
```
