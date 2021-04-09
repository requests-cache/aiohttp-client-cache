# Sphinx documentation build configuration file
import sys
from os.path import abspath, dirname, join

DOCS_DIR = abspath(dirname(__file__))
PROJECT_DIR = dirname(DOCS_DIR)
PACKAGE_DIR = join(PROJECT_DIR, 'aiohttp_client_cache')

# Add project path so we can import our package
sys.path.insert(0, PROJECT_DIR)
from aiohttp_client_cache import __version__  # noqa

# General project info
project = 'aiohttp-client-cache'
copyright = '2021 Jordan Cook'
needs_sphinx = '3.0'
version = release = __version__

# General source info
master_doc = 'index'
source_suffix = ['.rst', '.md']
html_static_path = ['_static']
templates_path = ['_templates']

# Sphinx extension modules
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.autosectionlabel',
    'sphinx.ext.autosummary',
    'sphinx.ext.intersphinx',
    'sphinx.ext.napoleon',
    # 'sphinx.ext.viewcode',
    'sphinx_autodoc_typehints',
    'sphinx_automodapi.automodapi',
    'sphinx_copybutton',
    'sphinxcontrib.apidoc',
    'm2r2',
]

# Enable automatic links to other projects' Sphinx docs
intersphinx_mapping = {
    'aioboto3': ('https://aioboto3.readthedocs.io/en/latest/', None),
    'aiohttp': ('https://docs.aiohttp.org/en/stable/', None),
    'aioredis': ('https://aioredis.readthedocs.io/en/stable/', None),
    'aiosqlite': ('https://aiosqlite.omnilib.dev/en/latest/', None),
    'botocore': ('http://botocore.readthedocs.io/en/latest/', None),
    'motor': ('https://motor.readthedocs.io/en/stable/', None),
    'pymongo': ('https://pymongo.readthedocs.io/en/stable/', None),
    'python': ('https://docs.python.org/3', None),
    'redis': ('https://redis-py.readthedocs.io/en/stable/', None),
}

# Exclude modules with manually formatted docs and documentation utility modules
exclude_patterns = [
    '_build',
    'modules/aiohttp_client_cache.rst',
    'modules/aiohttp_client_cache.backends.rst',
    'modules/aiohttp_client_cache.session.rst',
    'modules/aiohttp_client_cache.docs.rst',
    'modules/aiohttp_client_cache.docs.connections.rst',
    'modules/aiohttp_client_cache.docs.forge_utils.rst',
]

# Enable Google-style docstrings
napoleon_google_docstring = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = False

# Strip prompt text when copying code blocks with copy button
copybutton_prompt_text = r'>>> |\.\.\. |\$ '
copybutton_prompt_is_regexp = True

# Move type hint info to function description instead of signature
autodoc_typehints = 'description'
set_type_checking_flag = True

# Use apidoc to auto-generate rst sources
apidoc_excluded_paths = ['forge_utils.py']
apidoc_extra_args = ['--private', '--templatedir=_templates']
apidoc_module_dir = PACKAGE_DIR
apidoc_module_first = True
apidoc_output_dir = 'modules'
apidoc_separate_modules = True
apidoc_toc_file = False
add_module_names = False

# Options for automodapi and autosectionlabel
automodsumm_inherited_members = False
autosectionlabel_prefix_document = True
numpydoc_show_class_members = False

# HTML theme settings
html_theme = 'sphinx_material'
html_show_sphinx = False
html_theme_options = {
    'color_primary': 'blue',
    'color_accent': 'light-blue',
    'globaltoc_depth': 3,
    'globaltoc_includehidden': False,
    'logo_icon': '&#xe2c0',
    'repo_url': 'https://github.com/JWCook/aiohttp-client-cache',
    'repo_name': project,
    'nav_title': project,
}
html_sidebars = {'**': ['logo-text.html', 'globaltoc.html', 'localtoc.html', 'searchbox.html']}


def setup(app):
    """Run some additional steps after the Sphinx builder is initialized"""
    app.connect('builder-inited', patch_automodapi)
    app.add_css_file('collapsible_container.css')


def patch_automodapi(app):
    """Monkey-patch the automodapi extension to exclude imported members

    https://github.com/astropy/sphinx-automodapi/blob/master/sphinx_automodapi/automodsumm.py#L135
    """
    from sphinx_automodapi import automodsumm
    from sphinx_automodapi.utils import find_mod_objs

    automodsumm.find_mod_objs = lambda *args: find_mod_objs(args[0], onlylocals=True)
