# History

## 0.4.0 (2021-05-TBD)
* Add optional support for the following **request** headers:
    * `Cache-Control: max-age`
    * `Cache-Control: no-cache`
    * `Cache-Control: no-store`
* Add optional support for the following **response** headers:
    * `Cache-Control: max-age`
    * `Cache-Control: no-store`
    * `Expires`
* Add support for HTTP timestamps (RFC 5322) in ``expire_after`` parameters
* Packaging is now handled with Poetry. For users, installation still works the same. For developers,
  see [Contributing Guide](https://aiohttp-client-cache.readthedocs.io/en/latest/contributing.html) for details

## 0.3.0 (2021-04-09)
[See all issues & PRs for v0.3](https://github.com/JWCook/aiohttp-client-cache/milestone/2?closed=1)

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
[See all issues & PRs for v0.2](https://github.com/JWCook/aiohttp-client-cache/milestone/1?closed=1)

* Refactor SQLite backend to use `aiosqlite` for async cache operations
* Refactor MongoDB backend to use `motor` for async cache operations
* Refactor Redis backend to use `aiosqlite` for async cache operations
* Add integration tests and `docker-compose` for local test servers

## 0.1.0 (2020-11-14)
* Initial fork from [`requests-cache`](https://github.com/reclosedev/requests-cache)
* First pass at a general refactor and conversion from `requests` to `aiohttp`
* Basic features are functional, but some backends do not actually operate asynchronously
