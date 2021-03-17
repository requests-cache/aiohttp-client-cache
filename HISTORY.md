# History

## 0.3.0 (TBD)
[See all issues & PRs here](https://github.com/JWCook/aiohttp-client-cache/milestone/2?closed=1)

* Add support for setting different expiration times based on URL patterns
* Add support for serializing/deserializing `ClientSession.links`
* Add case-insensitive response headers for compatibility with aiohttp.ClientResponse.headers

## 0.2.0 (2021-02-28)
[See all issues & PRs here](https://github.com/JWCook/aiohttp-client-cache/milestone/1?closed=1)

* Refactor SQLite backend to use `aiosqlite` for async cache operations
* Refactor MongoDB backend to use `motor` for async cache operations
* Refactor Redis backend to use `aiosqlite` for async cache operations
* Add integration tests and `docker-compose` for local test servers

## 0.1.0 (2020-11-14)
* Initial PyPI release
* First pass at a general refactor and conversion from `requests` to `aiohttp`
* Basic features are functional, but some backends do not actually operate asynchronously

## requests-cache
See `requests-cache` [development history](https://github.com/reclosedev/requests-cache/blob/master/HISTORY.rst)
for details on prior changes.
