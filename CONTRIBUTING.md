# Contributing

## Installation
To set up for local development:

```bash
$ git clone https://github.com/JWCook/aiohttp-client-cache
$ cd aiohttp-client-cache
$ pip install -Ue ".[dev]"
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

Documentation is automatically built by ReadTheDocs whenever code is merged into the `main` branch.


## Releases
Releases are built and published to pypi based on **git tags.**
[Milestones](https://github.com/JWCook/aiohttp-client-cache/milestones) will be used to track
progress on major and minor releases.

