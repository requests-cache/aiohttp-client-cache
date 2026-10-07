# Sphinx documentation build configuration file
from importlib.metadata import version as pkg_version
from pathlib import Path

DOCS_DIR = Path(__file__).parent.absolute()
PROJECT_DIR = DOCS_DIR.parent
PACKAGE_DIR = PROJECT_DIR / 'aiohttp_client_cache'

# General project info
project = 'aiohttp-client-cache'
needs_sphinx = '9.0'
version = release = pkg_version('aiohttp-client-cache')

# General source info
master_doc = 'index'
source_suffix = {'.rst': 'restructuredtext', '.md': 'restructuredtext'}
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
    'botocore': ('https://botocore.amazonaws.com/v1/documentation/api/latest', None),
    'boto3': ('https://boto3.amazonaws.com/v1/documentation/api/latest', None),
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

# Use apidoc to auto-generate rst sources
apidoc_excluded_paths = ['signatures.py']
apidoc_module_dir = str(PACKAGE_DIR)
apidoc_module_first = True
apidoc_output_dir = 'modules'
apidoc_separate_modules = True
apidoc_template_dir = '_templates/apidoc'
apidoc_toc_file = False
add_module_names = False

# Options for automodapi and autosectionlabel
automodsumm_inherited_members = False
autosectionlabel_prefix_document = True

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
