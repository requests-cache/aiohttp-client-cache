# History

## 0.12.3 (2024-10-04)

- Revert some changes from `v0.12.0`, and add alternative fix for compatibility with aiohttp 3.10.6+

## 0.12.2 (2024-10-02)

- Fixed a regression in `v0.12.0` when the `request_info` property was unavailable on a cached response. (!260)

## 0.12.1 (2024-10-02)

- Fixed `get_encoding()` access after unpickling. (#256)

## 0.12.0 (2024-10-01)

- Add support for Python 3.13
- Fix `CachedResponse.is_expired` check to consider any errors as "expired". (!252)
- Fix compatibility with aiohttp 3.10.6+ (#251)
  - Now `CachedResponse` inherits from the `aiohttp.ClientResponse`.

## 0.11.1 (2024-08-01)

- Fix compatibility with aiosqlite 0.20
- Add complete type hints for `CachedSession.get()`, `post()`, etc. for compatibility with aiohttp 3.10
- Remove usage of `datetime.utcnow()` (deprecated in python 3.12)

## 0.11.0 (2024-02-08)

- Add support for Python 3.12.
- Add a Docker Compose file with [DragonflyDB](https://www.dragonflydb.io/) service that can be used as a Redis drop-in replacement.
- Add minor performance improvements for MongoDB backend. (!203)

## Deprecations and Removals

- Drop support for Python 3.7.

## 0.10.0 (2023-10-30)

- Add support for conditional requests with `ETag` and `Last-Modified`
- If a DynamoDB item exceeds the max size (400KB), skip writing to the cache and log a warning instead of raising an error
- Add `CachedResponse.closed` attribute for compatibility with `aiohttp.ClientResponse`
- Close `aiosqlite` thread if it's still running when session object is deleted
- Move redirects cache for `FileBackend` into same directory as cached response files
- Fix issue in which `CachedSession.disabled()` prevents only cache read but not write

## 0.9.1 (2023-09-20)

- Remove unintended optional dependencies in both PyPI and conda-forge packages

## 0.9.0 (2023-09-19)

- Add compatibility with Sentry python SDK
- Add `autoclose` option to `CacheBackend` to close backend connections when the session context exits.
  - Enabled by default for SQLite backend, and disabled by default for other backends.
- `python-forge` is no longer required and is now an optional dependency
- Fix reading response content multiple times for memory backend

## 0.8.2 (2023-07-14)

- Add some missing type annotations to backend classes
- Fix passing connection parameters to MongoDB backend
- Revert closing backend connections on session context exit
- Fix `CachedResponse.close()` method to match `ClientResponse.close()`

## 0.8.1 (2023-01-05)

- For SQLite backend, close database connection on `ClientSession` context exit

## 0.8.0 (2022-12-29)

- Lazily initialize and reuse SQLite connection objects
- Fix `AttributeError` when using a response cached with an older version of `attrs`
- Fix concurrent usage of `SQLiteCache.bulk_commit()`
- Add `fast_save` option for `SQLiteCache` (`PRAGMA` setting to improve write performance, with some tradeoffs)

## 0.7.3 (2022-07-31)

- Remove upper version constraint for `attrs` dependency

## 0.7.2 (2022-07-13)

- Fix `TypeError` bug when using `expire_after` param with `CachedSession._request()`

## 0.7.1 (2022-06-22)

- Fix possible deadlock with `SQLiteCache.init_db()` and `clear()`

## 0.7.0 (2022-05-21)

[See all issues & PRs for v0.7](https://github.com/requests-cache/aiohttp-client-cache/milestone/6?closed=1)

- Support manually saving a response to the cache with `CachedSession.cache.save_response()`
- Add compatibility with aioboto3 0.9+
- Migrate to redis-py 4.2+ (merged with aioredis)
- Add missing `aiosqlite` dependency for filesystem backend
- Add missing `CachedResponse` properties derived from headers:
  - `charset`
  - `content_length`
  - `content_type`
- Add support for async filter functions
- Move repo to [requests-cache](https://github.com/requests-cache) organization

## 0.6.1 (2022-02-13)

- Migrate to aioredis 2.0
- Fix issue with restoring empty session cookies

## 0.6.0 (2022-02-12)

[See all issues & PRs for v0.6](https://github.com/requests-cache/aiohttp-client-cache/milestone/5?closed=1)

- Add a `bulk_delete()` method for all backends to improve performance of `delete_expired_responses()`
- Update session cookies after fetching cached responses with cookies
- Update session cookies after fetching cached responses with _redirects_ with cookies
- Add support for additional request parameter types that `aiohttp` accepts:
  - Strings
  - `(key, value)` sequences
  - Non-`dict` `Mapping` objects
- Fix URL normalization for `MultiDict` objects with duplicate keys
  - E.g., so `http://url.com?foo=bar&foo=baz` is cached separately from `http://url.com?foo=bar`
- Update `ignored_params` to also apply to headers (if `include_headers=True`)

## 0.5.2 (2021-11-03)

- Fix compatibility with aiohttp 3.8

## 0.5.1 (2021-09-10)

- Fix issue with request params duplicated from request URL

## 0.5.0 (2021-09-01)

[See all issues & PRs for v0.5](https://github.com/requests-cache/aiohttp-client-cache/milestone/4?closed=1)

- Add a filesystem backend
- Add support for streaming requests
- Add `RedisBackend.close()` method
- Add `MongoDBPickleCache.values()` method that deserializes items
- Allow `BaseCache.has_url()` and `delete_url()` to take all the same parameters as `create_key()`
- Improve normalization for variations of URLs & request parameters
- Fix handling of request body when it has already been serialized
- Fix bug enabling Cache-Control support by default
- Add some missing no-op methods to `CachedResponse` for compatibility with `ClientResponse`

---

## 0.4.3 (2021-07-27)

- Fix bug in which reponse header `Expires` was used for cache expiration even with `cache_control=False`
- Fix bug in which HTTP dates parsed from response headers weren't converted to UTC
- Add handling for invalid timestamps in `CachedResponse.is_expired`

## 0.4.2 (2021-07-26)

- Fix handling of `CachedResponse.encoding` when the response body is `None`

## 0.4.1 (2021-07-09)

- Fix initialziation of `SQLiteBackend` so it can be created outside main event loop

## 0.4.0 (2021-05-12)

[See all issues & PRs for v0.4](https://github.com/requests-cache/aiohttp-client-cache/milestone/3?closed=1)

- Add optional support for the following **request** headers:
  - `Cache-Control: max-age`
  - `Cache-Control: no-cache`
  - `Cache-Control: no-store`
- Add optional support for the following **response** headers:
  - `Cache-Control: max-age`
  - `Cache-Control: no-store`
  - `Expires`
- Add support for HTTP timestamps (RFC 5322) in `expire_after` parameters
- Add a `use_temp` option to `SQLiteBackend` to use a tempfile
- Packaging is now handled with Poetry. For users, installation still works the same. For developers,
  see [Contributing Guide](https://aiohttp-client-cache.readthedocs.io/en/stable/contributing.html) for details
- Published package on [conda-forge](https://anaconda.org/conda-forge/aiohttp-client-cache)

## 0.3.0 (2021-04-09)

[See all issues & PRs for v0.3](https://github.com/requests-cache/aiohttp-client-cache/milestone/2?closed=1)

- Add async implementation of DynamoDb backend
- Add support for expiration for individual requests
- Add support for expiration based on URL patterns
- Add support for serializing/deserializing `ClientSession.links`
- Add case-insensitive response headers for compatibility with aiohttp.ClientResponse.headers
- Add optional integration with `itsdangerous` for safer serialization
- Add `CacheBackend.get_urls()` to get all urls currently in the cache
- Add some default attributes (`from_cache, is_expired`, etc.) to returned ClientResponse objects
- Allow passing all backend-specific connection kwargs via CacheBackend
- Add support for `json` request body
- Convert all `keys()` and `values()` methods into async generators
- Fix serialization of Content-Disposition
- Fix filtering ignored parameters for request body (`data` and `json`)
- Add user guide, more examples, and other project docs

## 0.2.0 (2021-02-28)

[See all issues & PRs for v0.2](https://github.com/requests-cache/aiohttp-client-cache/milestone/1?closed=1)

- Refactor SQLite backend to use `aiosqlite` for async cache operations
- Refactor MongoDB backend to use `motor` for async cache operations
- Refactor Redis backend to use `aiosqlite` for async cache operations
- Add integration tests and `docker-compose` for local test servers

## 0.1.0 (2020-11-14)

- Initial fork from [`requests-cache`](https://github.com/reclosedev/requests-cache)
- First pass at a general refactor and conversion from `requests` to `aiohttp`
- Basic features are functional, but some backends do not actually operate asynchronously
