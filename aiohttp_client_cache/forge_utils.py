from typing import Callable, Iterable

import forge


def extend_signature(template_func: Callable) -> Callable:
    """Copy another function's signature, and extend it with the wrapped function's signature"""

    def wrapper(target_func: Callable):
        revision = get_combined_revision([template_func, target_func])
        return revision(target_func)

    return wrapper


def get_combined_revision(functions: Iterable[Callable]) -> forge.Revision:
    """Combine the parameters of all revisions into a single revision"""
    params = {}
    for func in functions:
        params.update(forge.copy(func).signature.parameters)
    return forge.sign(*params.values())
