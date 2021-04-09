# History

## 0.3.0 (2021-04-TBD)
[See all issues & PRs for v0.3](https://github.com/JWCook/aiohttp-client-cache/milestone/2?closed=1)

* Add async implementation of DynamoDb backend
* Add support for expiration for individual requests
* Add support for expiration based on URL patterns
* Add support for serializing/deserializing `ClientSession.links`
* Add case-insensitive response headers for compatibility with aiohttp.ClientResponse.headers
* Add optional integration with `itsdangerous` for safer serialization
* Add `CacheBackend.get_urls()` to get all urls currently in the cache
* Allow passing all connection kwargs (for SQLite, Redis, and MongoDB connection methods) via CacheBackend
* Add support for `json` request body
* Convert all `keys()` and `values()` methods into async generators
* Fix serialization of Content-Disposition
* Fix filtering ignored parameters for request body (`data` and `json`)

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
