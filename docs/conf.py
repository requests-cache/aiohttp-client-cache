# Sphinx documentation build configuration file
import sys
from os.path import abspath, dirname, join

DOCS_DIR = abspath(dirname(__file__))
PROJECT_DIR = dirname(DOCS_DIR)
PACKAGE_DIR = join(PROJECT_DIR, 'aiohttp_client_cache')

# Add project path so we can import our package
sys.path.insert(0, PROJECT_DIR)
from aiohttp_client_cache import __version__  # noqa

# General information about the project.
project = 'aiohttp-client-cache'
copyright = '2021 Jordan Cook'
needs_sphinx = '3.0'
master_doc = 'index'
source_suffix = ['.rst', '.md']
version = release = __version__
html_static_path = ['_static']
templates_path = ['_templates']

# Exclude the generated aiohttp_client_cache.rst, which will just contain top-level __init__ info
exclude_patterns = ['_build', 'modules/aiohttp_client_cache.rst']

# Sphinx extension modules
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.intersphinx',
    'sphinx.ext.napoleon',
    # 'sphinx.ext.viewcode',
    'sphinx_autodoc_typehints',
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

# Enable Google-style docstrings
napoleon_google_docstring = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = False
# numpydoc_show_class_members = False

# Strip prompt text when copying code blocks with copy button
copybutton_prompt_text = r'>>> |\.\.\. |\$ '
copybutton_prompt_is_regexp = True

# Use apidoc to auto-generate rst sources
apidoc_excluded_paths = ['api_docs.py']
apidoc_extra_args = ['--private']
apidoc_module_dir = PACKAGE_DIR
apidoc_module_first = True
apidoc_output_dir = 'modules'
apidoc_separate_modules = True
apidoc_toc_file = False

# Move type hint info to function description instead of signature
autodoc_typehints = 'description'
set_type_checking_flag = True

# HTML theme settings
pygments_style = 'sphinx'
html_theme = 'sphinx_material'
html_theme_options = {
    'color_primary': 'blue',
    'color_accent': 'light-blue',
    'globaltoc_depth': 1,
    'globaltoc_includehidden': False,
    'logo_icon': '&#xe1af',
    'repo_url': 'https://github.com/JWCook/aiohttp-client-cache',
    'repo_name': project,
    'nav_title': project,
}
html_sidebars = {'**': ['logo-text.html', 'globaltoc.html', 'localtoc.html', 'searchbox.html']}
