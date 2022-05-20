# Contributing Guide

## Dev Installation
To set up for local development (requires [poetry](https://python-poetry.org/docs/#installation)):

```bash
$ git clone https://github.com/requests-cache/aiohttp-client-cache
$ cd aiohttp-client-cache
$ poetry install -E backends -E docs
```

## Pre-commit hooks
CI jobs will run code style checks, type checks, linting, etc. If you would like to run these same
checks locally, you can use [pre-commit](https://github.com/pre-commit/pre-commit).
This is optional but recommended.

To install pre-commit hooks:
```bash
pre-commit install
```

To manually run checks on all files:
```bash
pre-commit run --all-files
# Alternative alias with nox:
nox -e lint
```

To disable pre-commit hooks:
```bash
pre-commit uninstall
```

## Testing
### Test Layout
Tests are divided into unit and integration tests:
* Unit tests can be run without any additional setup, and **don't depend on any external services**
* Integration tests **depend on additional services**, which are easiest to run using Docker
    (see Integration Tests section below)

### Running Tests
* Run `pytest` to run all tests
* Run `pytest test/unit` to run only unit tests
* Run `pytest test/integration` to run only integration tests

For CI jobs (including PRs), these tests will be run for each supported python version.
You can use [nox](https://nox.thea.codes) to do this locally, if needed:
```bash
nox -e test
```

Or to run tests for a specific python version:
```bash
nox -e test-3.10
```

To generate a coverage report:
```bash
nox -e cov
```

See `nox --list` for a ful list of available commands.

### Integration Test Containers
A live web server and backend databases are required to run integration tests, and docker-compose
config is included to make this easier. First, [install docker](https://docs.docker.com/get-docker/)
and [install docker-compose](https://docs.docker.com/compose/install/).

Then, run:
```bash
docker-compose up -d
pytest test/integration
```

## Documentation
[Sphinx](http://www.sphinx-doc.org/en/master/) is used to generate documentation.

To build the docs locally:
```bash
$ nox -e docs
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
- Add unit test coverage for your changes
- If your changes add or modify user-facing behavior, add documentation describing those changes
- Submit the PR to be merged into the `main` branch.

## Releases
Releases are built and published to pypi based on **git tags.**
[Milestones](https://github.com/requests-cache/aiohttp-client-cache/milestones) will be used to track
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
