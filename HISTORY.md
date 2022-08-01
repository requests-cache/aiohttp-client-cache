# History

## 0.7.3 (2022-07-31)
* Remove upper version constraint for `attrs` dependency

## 0.7.2 (2022-07-13)
* Fix `TypeError` bug when using `expire_after` param with `CachedSession._request()`

## 0.7.1 (2022-06-22)
* Use `threading.RLock` for locking `SQLiteCache.init_db()` and `clear()`

## 0.7.0 (2022-05-21)
[See all issues & PRs for v0.7](https://github.com/requests-cache/aiohttp-client-cache/milestone/6?closed=1)
* Support manually saving a response to the cache with `CachedSession.cache.save_response()`
* Add compatibility with aioboto3 0.9+
* Migrate to redis-py 4.2+ (merged with aioredis)
* Add missing `aiosqlite` dependency for filesystem backend
* Add missing `CachedResponse` properties derived from headers:
  * `charset`
  * `content_length`
  * `content_type`
* Add support for async filter functions
* Move repo to [requests-cache](https://github.com/requests-cache) organization

### 0.6.1 (2022-02-13)
* Migrate to aioredis 2.0
* Fix issue with restoring empty session cookies

## 0.6.0 (2022-02-12)
[See all issues & PRs for v0.6](https://github.com/requests-cache/aiohttp-client-cache/milestone/5?closed=1)
* Add a `bulk_delete()` method for all backends to improve performance of `delete_expired_responses()`
* Update session cookies after fetching cached responses with cookies
* Update session cookies after fetching cached responses with _redirects_ with cookies
* Add support for additional request parameter types that `aiohttp` accepts:
  * Strings
  * `(key, value)` sequences
  * Non-`dict` `Mapping` objects
* Fix URL normalization for `MultiDict` objects with duplicate keys
  * E.g., so  `http://url.com?foo=bar&foo=baz` is cached separately from `http://url.com?foo=bar`
* Update `ignored_params` to also apply to headers (if `include_headers=True`)

### 0.5.2 (2021-11-03)
* Fix compatibility with aiohttp 3.8

### 0.5.1 (2021-09-10)
* Fix issue with request params duplicated from request URL

## 0.5.0 (2021-09-01)
[See all issues & PRs for v0.5](https://github.com/requests-cache/aiohttp-client-cache/milestone/4?closed=1)

* Add a filesystem backend
* Add support for streaming requests
* Add `RedisBackend.close()` method
* Add `MongoDBPickleCache.values()` method that deserializes items
* Allow `BaseCache.has_url()` and `delete_url()` to take all the same parameters as `create_key()`
* Improve normalization for variations of URLs & request parameters
* Fix handling of request body when it has already been serialized
* Fix bug enabling Cache-Control support by default
* Add some missing no-op methods to `CachedResponse` for compatibility with `ClientResponse`

---
### 0.4.3 (2021-07-27)
* Fix bug in which reponse header `Expires` was used for cache expiration even with `cache_control=False`
* Fix bug in which HTTP dates parsed from response headers weren't converted to UTC
* Add handling for invalid timestamps in `CachedResponse.is_expired`

### 0.4.2 (2021-07-26)
* Fix handling of `CachedResponse.encoding` when the response body is `None`

### 0.4.1 (2021-07-09)
* Fix initialziation of `SQLiteBackend` so it can be created outside main event loop

## 0.4.0 (2021-05-12)
[See all issues & PRs for v0.4](https://github.com/requests-cache/aiohttp-client-cache/milestone/3?closed=1)

* Add optional support for the following **request** headers:
    * `Cache-Control: max-age`
    * `Cache-Control: no-cache`
    * `Cache-Control: no-store`
* Add optional support for the following **response** headers:
    * `Cache-Control: max-age`
    * `Cache-Control: no-store`
    * `Expires`
* Add support for HTTP timestamps (RFC 5322) in ``expire_after`` parameters
* Add a `use_temp` option to `SQLiteBackend` to use a tempfile
* Packaging is now handled with Poetry. For users, installation still works the same. For developers,
  see [Contributing Guide](https://aiohttp-client-cache.readthedocs.io/en/latest/contributing.html) for details
* Published package on [conda-forge](https://anaconda.org/conda-forge/aiohttp-client-cache)

## 0.3.0 (2021-04-09)
[See all issues & PRs for v0.3](https://github.com/requests-cache/aiohttp-client-cache/milestone/2?closed=1)

* Add async implementation of DynamoDb backend
* Add support for expiration for individual requests
* Add support for expiration based on URL patterns
* Add support for serializing/deserializing `ClientSession.links`
* Add case-insensitive response headers for compatibility with aiohttp.ClientResponse.headers
* Add optional integration with `itsdangerous` for safer serialization
* Add `CacheBackend.get_urls()` to get all urls currently in the cache
* Add some default attributes (`from_cache, is_expired`, etc.) to returned ClientResponse objects
* Allow passing all backend-specific connection kwargs via CacheBackend
* Add support for `json` request body
* Convert all `keys()` and `values()` methods into async generators
* Fix serialization of Content-Disposition
* Fix filtering ignored parameters for request body (`data` and `json`)
* Add user guide, more examples, and other project docs

## 0.2.0 (2021-02-28)
[See all issues & PRs for v0.2](https://github.com/requests-cache/aiohttp-client-cache/milestone/1?closed=1)

* Refactor SQLite backend to use `aiosqlite` for async cache operations
* Refactor MongoDB backend to use `motor` for async cache operations
* Refactor Redis backend to use `aiosqlite` for async cache operations
* Add integration tests and `docker-compose` for local test servers

## 0.1.0 (2020-11-14)
* Initial fork from [`requests-cache`](https://github.com/reclosedev/requests-cache)
* First pass at a general refactor and conversion from `requests` to `aiohttp`
* Basic features are functional, but some backends do not actually operate asynchronously
