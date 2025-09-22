"""Notes:
* 'test' command: nox will use uv.lock to determine dependency versions
* 'lint' command: tools and environments are managed by pre-commit
* All other commands: the current environment will be used instead of creating new ones
"""

from os.path import join
from pathlib import Path
from shutil import rmtree

import nox

nox.options.reuse_existing_virtualenvs = True
nox.options.sessions = ['lint', 'cov']

DOCS_DIR = Path('docs')
LIVE_DOCS_PORT = 8181
LIVE_DOCS_IGNORE = ['*.pyc', '*.tmp', join('**', 'modules', '*')]
LIVE_DOCS_WATCH = ['aiohttp_client_cache', 'examples']
CLEAN_DIRS = ['dist', 'build', DOCS_DIR / '_build', DOCS_DIR / 'modules']

TEST_DIR = Path('test')
UNIT_TESTS = TEST_DIR / 'unit'
INTEGRATION_TESTS = TEST_DIR / 'integration'
COVERAGE_ARGS = (
    '--cov --cov-report=term --cov-report=html'  # Generate HTML + stdout coverage report
)
XDIST_ARGS = '--numprocesses=auto --dist=loadfile'  # Run tests in parallel, grouped by test module


@nox.session(python=['3.9', '3.10', '3.11', '3.12'])
def test(session):
    """Run tests for a specific python version"""
    test_paths = session.posargs or [UNIT_TESTS]
    session.run('uv', 'sync', '--python', session.python, '--only-dev', external=True)

    cmd = f'uv run pytest -rs {XDIST_ARGS}'
    session.run(*cmd.split(' '), *test_paths, external=True)


@nox.session(python=False)
def clean(session):
    """Clean up temporary build + documentation files"""
    for dir in CLEAN_DIRS:
        print(f'Removing {dir}')
        rmtree(dir, ignore_errors=True)  # type: ignore[arg-type]


@nox.session(python=False, name='cov')
def coverage(session):
    """Run tests and generate coverage report"""
    cmd_1 = f'uv run pytest {UNIT_TESTS} -rs {XDIST_ARGS} {COVERAGE_ARGS}'
    cmd_2 = f'uv run pytest {INTEGRATION_TESTS} -rs {XDIST_ARGS} {COVERAGE_ARGS} --cov-append'
    session.run(*cmd_1.split(' '), external=True)
    session.run(*cmd_2.split(' '), external=True)


@nox.session(python=False)
def docs(session):
    """Build Sphinx documentation"""
    cmd = 'uv run sphinx-build docs docs/_build/html -j auto'
    session.run(*cmd.split(' '), external=True)


@nox.session(python=False)
def livedocs(session):
    """Auto-build docs with live reload in browser.
    Add `--open` to also open the browser after starting.
    """
    args = ['-a']
    args += [f'--watch {pattern}' for pattern in LIVE_DOCS_WATCH]
    args += [f'--ignore {pattern}' for pattern in LIVE_DOCS_IGNORE]
    args += [f'--port {LIVE_DOCS_PORT}', '-j auto']
    if session.posargs == ['open']:
        args.append('--open-browser')

    clean(session)
    cmd = 'uv run sphinx-autobuild docs docs/_build/html ' + ' '.join(args)
    session.run(*cmd.split(' '), external=True)


@nox.session(python=False)
def lint(session):
    """Run linters and code formatters via pre-commit"""
    cmd = 'uv run pre-commit run --all-files'
    session.run(*cmd.split(' '), external=True)
