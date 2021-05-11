# Contributing Guide

## Dev Installation
To set up for local development (requires [poetry](https://python-poetry.org/docs/#installation)):

```bash
$ git clone https://github.com/JWCook/aiohttp-client-cache
$ cd aiohttp-client-cache
$ poetry install -E backends -E docs
```

## Pre-commit hooks
[Pre-commit](https://github.com/pre-commit/pre-commit) config is uncluded to run the same checks
locally that are run in CI jobs by GitHub Actions. This is optional but recommended.
```bash
$ pre-commit install --config .github/pre-commit.yml
```

To uninstall:
```bash
$ pre-commit uninstall
```

## Integration Tests
Local databases are required to run integration tests, and docker-compose config is included to make
this easier. First, [install docker](https://docs.docker.com/get-docker/) and
[install docker-compose](https://docs.docker.com/compose/install/).

Then, run:
```bash
$ docker-compose up -d
pytest test/integration
```

## Documentation
[Sphinx](http://www.sphinx-doc.org/en/master/) is used to generate documentation.

To build the docs locally:
```bash
$ make -C docs html
```

To preview:
```bash
# MacOS:
$ open docs/_build/index.html
# Linux:
$ xdg-open docs/_build/index.html
```

### Readthedocs
Documentation is automatically built and published by Readthedocs whenever code is merged into the
`main` branch.

Sometimes, there are differences in the Readthedocs build environment that can cause builds to
succeed locally but fail remotely. To help debug this, you can use the 
[readthedocs/build](https://github.com/readthedocs/readthedocs-docker-images) container to build
the docs. A configured build container is included in `docker-compose.yml` to simplify this.

Run with:
```bash
docker-compose up -d --build
docker exec readthedocs make all
```

## Pull Requests
Here are some general guidelines for submitting a pull request:

- If the changes are trivial, just briefly explain the changes in the PR description.
- Otherwise, please submit an issue describing the proposed change prior to submitting a PR.
- Please add unit test coverage and updated docs (if applicable) for your changes.
- Submit the PR to be merged into the `main` branch.

## Releases
Releases are built and published to pypi based on **git tags.**
[Milestones](https://github.com/JWCook/aiohttp-client-cache/milestones) will be used to track
progress on major and minor releases.

## Code Layout
Here is a brief overview of the main classes and modules. See [API Reference](https://aiohttp-client-cache.readthedocs.io/en/latest/reference.html) for more complete documentation.
* `session.CacheMixin`, `session.CachedSession`: A mixin and wrapper class, respectively, for `aiohttp.ClientSession`. There is little logic  here except wrapping `ClientSession._request()` with caching behavior.
* `response.CachedResponse`: A wrapper class built from an `aiohttp.ClientResponse`, with additional cache-related info. This is what is serialized and persisted to the cache.
* `backends.base.CacheBackend`: Most of the caching logic lives here, including saving and retrieving responses. It contains two `BaseCache` objects for storing responses and redirects, respectively.
* `backends.base.BaseCache`: Base class for lower-level storage operations, overridden by individual backends.
* Other modules under `backends.*`: Backend implementations that subclass `CacheBackend` + `BaseCache`
* `cache_control`: Utilities for determining cache expiration and other cache actions  
* `cache_keys`: Utilities for creating cache keys
