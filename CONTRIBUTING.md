# Contributing Guide

## Dev Installation

To set up for local development (requires [poetry](https://python-poetry.org/docs/#installation)):

```sh
$ git clone https://github.com/requests-cache/aiohttp-client-cache
$ cd aiohttp-client-cache
$ poetry install -E all
```

## Pre-commit hooks

CI jobs will run code style checks, type checks, linting, etc. If you would like to run these same
checks locally, you can use [pre-commit](https://github.com/pre-commit/pre-commit).
This is optional but recommended.

To install pre-commit hooks:

```sh
pre-commit install
```

To manually run checks on all files:

```sh
pre-commit run --all-files
# Alternative alias with nox:
nox -e lint
```

To disable pre-commit hooks:

```sh
pre-commit uninstall
```

## Testing

### Test Layout

Tests are divided into unit and integration tests:

- Unit tests can be run without any additional setup, and **don't depend on any external services**
- Integration tests **depend on additional services**, which are easiest to run using Docker
  (see Integration Tests section below)

### Running Tests

- Run `pytest` to run all tests
- Run `pytest test/unit` to run only unit tests
- Run `pytest test/integration` to run only integration tests

For CI jobs (including PRs), these tests will be run for each supported python version.
You can use [nox](https://nox.thea.codes) to do this locally, if needed:

```sh
nox -e test
```

Or to run tests for a specific python version:

```sh
nox -e test-3.10
```

To generate a coverage report:

```sh
nox -e cov
```

See `nox --list` for a ful list of available commands.

### Integration Test Containers

A live web server and backend databases are required to run integration tests, and docker-compose
config is included to make this easier. First, [install docker](https://docs.docker.com/get-docker/)
and [install docker-compose](https://docs.docker.com/compose/install/).

Then, run:

```sh
docker-compose up -d
pytest test/integration
```

To test DragonflyDB you need to stop a Redis container (if running) and run `docker compose -f dragonflydb.yaml up`.
No other changes are required, you can run related tests with e.g. `pytest test -k redis`.

## Documentation

[Sphinx](http://www.sphinx-doc.org/en/master/) is used to generate documentation.

First, install documentation dependencies:

```sh
$ poetry install -E all --with docs
```

To build the docs locally:

```sh
$ nox -e docs
```

To preview:

```sh
# MacOS:
$ open docs/_build/index.html
# Linux:
$ xdg-open docs/_build/html/index.html
```

### Readthedocs

Documentation is automatically built and published by Readthedocs whenever code is merged into the
`main` branch.

Sometimes, there are differences in the Readthedocs build environment that can cause builds to
succeed locally but fail remotely. To help debug this, you can use the
[readthedocs/build](https://github.com/readthedocs/readthedocs-docker-images) container to build
the docs. A configured build container is included in `docker-compose.yml` to simplify this.

Run with:

```sh
docker compose up -d --build
docker exec readthedocs make all
```

## Pull Requests

Here are some general guidelines for submitting a pull request:

- If the changes are trivial, just briefly explain the changes in the PR description.
- Otherwise, please submit an issue describing the proposed change prior to submitting a PR.
- Add unit test coverage for your changes
- If your changes add or modify user-facing behavior, add documentation describing those changes
- Submit the PR to be merged into the `main` branch.

## Notes for Maintainers

### Releases

- Releases are built and published to PyPI based on **git tags.**
- [Milestones](https://github.com/requests-cache/aiohttp-client-cache/milestones) will be used to track
  progress on major and minor releases.
- GitHub Actions will build and deploy packages to PyPI on tagged commits
  on the `main` branch.

Release steps:

- Update the version in both `pyproject.toml` and `aiohttp_client_cache/__init__.py`
- Make sure the release notes in `HISTORY.md` are up to date
- Push a new tag, e.g.: `git tag v0.1.0 && git push origin v0.1.0`
- This will trigger a deployment. Verify that this completes successfully and that the new version can be installed from pypi with `pip install`
- A [readthedocs build](https://readthedocs.org/projects/aiohttp-client-cache/builds/) will be triggered by the new tag. Verify that this completes successfully.

Downstream builds:

- We also maintain a [Conda package](https://anaconda.org/conda-forge/aiohttp-client-cache), which is automatically built and published by conda-forge whenever a new release is published to PyPI. The [feedstock repo](https://github.com/conda-forge/aiohttp-client-cache-feedstock) only needs to be updated manually if there are changes to dependencies.
- For reference: [repology](https://repology.org/project/python:aiohttp-client-cache) lists additional downstream packages maintained by other developers.

### Code Layout

Here is a brief overview of the main classes and modules. See [API Reference](https://aiohttp-client-cache.readthedocs.io/en/latest/reference.html) for more complete documentation.

- `session.CacheMixin`, `session.CachedSession`: A mixin and wrapper class, respectively, for `aiohttp.ClientSession`. There is little logic here except wrapping `ClientSession._request()` with caching behavior.
- `response.CachedResponse`: A wrapper class built from an `aiohttp.ClientResponse`, with additional cache-related info. This is what is serialized and persisted to the cache.
- `backends.base.CacheBackend`: Most of the caching logic lives here, including saving and retrieving responses. It contains two `BaseCache` objects for storing responses and redirects, respectively.
- `backends.base.BaseCache`: Base class for lower-level storage operations, overridden by individual backends.
- Other modules under `backends.*`: Backend implementations that subclass `CacheBackend` + `BaseCache`
- `cache_control`: Utilities for determining cache expiration and other cache actions
- `cache_keys`: Utilities for creating cache keys
