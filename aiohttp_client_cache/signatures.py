"""Utilities for dynamically modifying function signatures.

The purpose of this is to generate thorough documentation of arguments without a ton of
copy-pasted text. This applies to both Sphinx docs hosted on readthedocs, as well as autocompletion,
type checking, etc. within an IDE or other editor.

Currently this is used to add the following backend-specific connection details:

* Function signatures
* Type annotations
* Argument docs
"""

from __future__ import annotations

import inspect
import re
from logging import getLogger
from typing import Callable

AUTOMETHOD_INIT = '.. automethod:: __init__'
logger = getLogger(__name__)


def extend_signature(super_function: Callable, *extra_functions: Callable) -> Callable:
    """A function decorator that modifies the target function's signature and docstring with:

    * Params from superclass
    * Params from target function
    * (optional) Params from additional functions called by the target function

    This also makes ``forge`` optional. If it's not installed, or if there's a problem with
    modifying a signature, this will just log the error and return the function with its original
    signature.
    """

    def wrapper(target_function: Callable):
        try:
            target_function = copy_docstrings(target_function, super_function, *extra_functions)
            revision = get_combined_revision(target_function, super_function, *extra_functions)
            return revision(target_function)
        except Exception as e:
            logger.debug(e)
            return target_function

    return wrapper


def get_combined_revision(*functions: Callable):
    """Combine the parameters of all revisions into a single revision"""
    import forge

    params = {}
    for func in functions:
        params.update(forge.copy(func).signature.parameters)
    params = deduplicate_kwargs(params)
    return forge.sign(*params.values())


def deduplicate_kwargs(params: dict) -> dict:
    """If a list of params contains one or more variadic keyword args (e.g., ``**kwargs``),
    ensure there are no duplicates and move it to the end.
    """
    import forge

    # Check for kwargs by param type instead of by name
    has_var_kwargs = False
    for k, v in params.copy().items():
        if v.kind == inspect.Parameter.VAR_KEYWORD:
            has_var_kwargs = True
            params.pop(k)

    # If it was present, add kwargs as the last param
    if has_var_kwargs:
        params.update(forge.kwargs)
    return params


def copy_docstrings(target_function: Callable, *template_functions: Callable) -> Callable:
    """Copy 'Args' documentation from one or more template functions to a target function.
    Assumes Google-style docstrings.

    Args:
        target_function: Function to modify
        template_functions: Functions containing docstrings to apply to ``target_function``

    Returns:
        Target function with modified docstring
    """
    # Start with initial function description
    docstring, args_section, return_section = _split_docstring(target_function.__doc__)

    # Combine and insert 'Args' section
    args_sections = [args_section]
    args_sections += [_split_docstring(func.__doc__)[1] for func in template_functions]
    docstring += '\n\nArgs:\n' + _combine_args_sections(*args_sections)

    # Insert 'Returns' section, if present
    if return_section:
        docstring += f'\n\nReturns:\n    {return_section}'

    target_function.__doc__ = docstring
    return target_function


def _split_docstring(docstring: str | None = None) -> tuple[str, str, str]:
    """Split a docstring into the following sections, if present:

    * Function summary
    * Argument descriptions
    * Return value description
    """
    summary = docstring or ''
    args_section = return_section = ''
    if 'Returns:' in summary:
        summary, return_section = summary.split('Returns:')
    if 'Args:' in summary:
        summary, args_section = summary.split('Args:')

    def fmt(chunk):
        return inspect.cleandoc(chunk.strip())

    return fmt(summary), fmt(args_section), fmt(return_section)


def _combine_args_sections(*args_sections: str) -> str:
    """Combine 'Args' sections from multiple functions into one section, removing any duplicates"""
    # Ensure one line per arg
    args_section = '\n'.join(args_sections).strip()
    args_section = re.sub('\n\\s+', ' ', args_section)

    # Split into key-value pairs to remove any duplicates; if so, keep the first one
    args: dict[str, str] = {}
    for line in args_section.splitlines():
        k, v = line.split(':', 1)
        args.setdefault(k.strip(), v.strip())

    return '\n'.join([f'    {k}: {v}' for k, v in args.items()])
