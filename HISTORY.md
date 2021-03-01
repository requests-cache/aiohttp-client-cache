# History

## 0.2.0 (2021-02-28)
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
