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
needs_sphinx = '5.0'
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
    'sphinx_autodoc_typehints',
    'sphinx_automodapi.automodapi',
    'sphinx_automodapi.smart_resolver',
    'sphinx_copybutton',
    'sphinx_inline_tabs',
    'sphinxcontrib.apidoc',
    'myst_parser',
]

# Enable automatic links to other projects' Sphinx docs
intersphinx_mapping = {
    'aioboto3': ('https://aioboto3.readthedocs.io/en/latest/', None),
    'aiohttp': ('https://docs.aiohttp.org/en/stable/', None),
    'aiosqlite': ('https://aiosqlite.omnilib.dev/en/latest/', None),
    'botocore': ('http://botocore.readthedocs.io/en/latest/', None),
    'boto3': ('https://boto3.amazonaws.com/v1/documentation/api/latest', None),
    'motor': ('https://motor.readthedocs.io/en/stable/', None),
    'pymongo': ('https://pymongo.readthedocs.io/en/stable/', None),
    'python': ('https://docs.python.org/3', None),
    'redis': ('https://redis-py.readthedocs.io/en/stable/', None),
    'yarl': ('https://yarl.aio-libs.org/en/latest/', None),
}

# MyST extensions
myst_enable_extensions = [
    'colon_fence',
    'html_image',
    'linkify',
    'replacements',
    'smartquotes',
]

# Exclude modules with manually formatted docs and documentation utility modules
exclude_patterns = [
    '_build',
    'modules/aiohttp_client_cache.rst',
    'modules/aiohttp_client_cache.backends.rst',
    'modules/aiohttp_client_cache.session.rst',
    'modules/aiohttp_client_cache.signatures.rst',
]

# napoleon settings
napoleon_google_docstring = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = False
napoleon_use_param = True

# Strip prompt text when copying code blocks with copy button
copybutton_prompt_text = r'>>> |\.\.\. |\$ '
copybutton_prompt_is_regexp = True

# Move type hint info to function description instead of signature
autodoc_typehints = 'description'
always_document_param_types = True
set_type_checking_flag = False

# Use apidoc to auto-generate rst sources
apidoc_excluded_paths = ['forge_utils.py']
apidoc_module_dir = PACKAGE_DIR
apidoc_module_first = True
apidoc_output_dir = 'modules'
apidoc_separate_modules = True
apidoc_template_dir = '_templates/apidoc'
apidoc_toc_file = False
add_module_names = False

# Options for automodapi and autosectionlabel
automodsumm_inherited_members = False
autosectionlabel_prefix_document = True
numpydoc_show_class_members = False

# HTML general settings
# html_favicon = join('images', 'favicon.ico')
html_js_files = ['collapsible_container.js']
html_css_files = ['collapsible_container.css', 'table.css']
html_show_sphinx = False
pygments_style = 'friendly'
pygments_dark_style = 'material'

# HTML theme settings
html_theme = 'furo'
html_theme_options = {
    # 'light_css_variables': {
    #     'color-brand-primary': '#00766c',  # MD light-blue-600; light #64d8cb | med #26a69a
    #     'color-brand-content': '#006db3',  # MD teal-400;       light #63ccff | med #039be5
    # },
    # 'dark_css_variables': {
    #     'color-brand-primary': '#64d8cb',
    #     'color-brand-content': '#63ccff',
    # },
    'sidebar_hide_name': False,
}


def setup(app):
    """Run some additional steps after the Sphinx builder is initialized"""
    app.connect('builder-inited', patch_automodapi)


def patch_automodapi(app):
    """Monkey-patch the automodapi extension to exclude imported members

    See: https://github.com/astropy/sphinx-automodapi/issues/119
    """
    from sphinx_automodapi import automodsumm
    from sphinx_automodapi.utils import find_mod_objs

    def find_local_mod_objs(*args, **kwargs):
        kwargs['onlylocals'] = True
        return find_mod_objs(*args, **kwargs)

    automodsumm.find_mod_objs = find_local_mod_objs
