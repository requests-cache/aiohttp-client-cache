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


def install_deps(session):
    """Install project and test dependencies into a test-specific virtualenv using uv"""
    session.env['UV_PROJECT_ENVIRONMENT'] = session.virtualenv.location
    session.run_install(
        'uv',
        'sync',
        '--frozen',
        '--all-extras',
    )


@nox.session(python=['3.9', '3.10', '3.11', '3.12', '3.13', '3.14'])
def test(session):
    """Run tests for a specific python version"""
    test_paths = session.posargs or [UNIT_TESTS]
    install_deps(session)
    cmd = f'pytest -rs {XDIST_ARGS}'
    session.run(*cmd.split(' '), *test_paths)


@nox.session(python=False)
def clean(session):
    """Clean up temporary build + documentation files"""
    for dir in CLEAN_DIRS:
        print(f'Removing {dir}')
        rmtree(dir, ignore_errors=True)  # type: ignore[arg-type]


@nox.session(python=False, name='cov')
def coverage(session):
    """Run tests and generate coverage report"""
    cmd_1 = f'pytest {UNIT_TESTS} -rs {XDIST_ARGS} {COVERAGE_ARGS}'
    cmd_2 = f'pytest {INTEGRATION_TESTS} -rs {XDIST_ARGS} {COVERAGE_ARGS} --cov-append'
    session.run(*cmd_1.split(' '))
    session.run(*cmd_2.split(' '))


@nox.session(python=False)
def docs(session):
    """Build Sphinx documentation"""
    cmd = 'sphinx-build docs docs/_build/html -j auto'
    session.run(*cmd.split(' '))


@nox.session(python=False)
def livedocs(session):
    """Auto-build docs with live reload in browser.
    Add `--open` to also open the browser after starting.
    """
    args = ['-a']
    args += [f'--watch {pattern}' for pattern in LIVE_DOCS_WATCH]
    args += [f'--ignore {pattern}' for pattern in LIVE_DOCS_IGNORE]
    args += [f'--port {LIVE_DOCS_PORT}', '--host 0.0.0.0', '-j auto']
    if session.posargs == ['open']:
        args.append('--open-browser')

    clean(session)
    cmd = 'sphinx-autobuild docs docs/_build/html ' + ' '.join(args)
    session.run(*cmd.split(' '))


@nox.session(python=False)
def lint(session):
    """Run linters and code formatters via pre-commit"""
    session.run('pre-commit', 'run', '--all-files')
