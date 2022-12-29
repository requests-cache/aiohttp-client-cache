"""Utilities for dynamically modifying function signatures.

The purpose of this is to generate thorough documentation of arguments without a ton of
copy-pasted text. This applies to both Sphinx docs hosted on readthedocs, as well as autocompletion,
type checking, etc. within an IDE or other editor.

Currently this is used to add the following backend-specific connection details:

* Function signatures
* Type annotations
* Argument docs
"""
import inspect
import re
from logging import getLogger
from typing import TYPE_CHECKING, Callable, Dict, Mapping, Optional, Tuple, Type, Union

if TYPE_CHECKING:
    from botocore.client import Config

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
            logger.exception(e)
            return target_function

    return wrapper


def extend_init_signature(super_class: Type, *extra_functions: Callable) -> Callable:
    """A class decorator that behaves like :py:func:`.extend_signature`, but modifies a class
    docstring and its ``__init__`` function signature.
    """

    def wrapper(target_class: Type):
        try:
            # Modify init signature + docstring
            revision = extend_signature(super_class.__init__, *extra_functions)
            target_class.__init__ = revision(target_class.__init__)
            # Include init docs in class docs
            target_class.__doc__ = target_class.__doc__ or ''
            if AUTOMETHOD_INIT not in target_class.__doc__:
                target_class.__doc__ += f'\n\n    {AUTOMETHOD_INIT}\n'
            return target_class
        except Exception as e:
            logger.exception(e)
            return target_class

    return wrapper


def copy_signature(template_function: Callable, include=None, exclude=None) -> Callable:
    """A wrapper around :py:func:`forge.copy` that silently fails if ``forge`` is not installed"""

    def wrapper(target_function: Callable):
        try:
            import forge
        except ImportError:
            return target_function

        revision = forge.copy(template_function, include=include, exclude=exclude)
        return revision(target_function)

    return wrapper


def get_combined_revision(*functions: Callable):
    """Combine the parameters of all revisions into a single revision"""
    import forge

    params = {}
    for func in functions:
        params.update(forge.copy(func).signature.parameters)
    params = deduplicate_kwargs(params)
    return forge.sign(*params.values())


def deduplicate_kwargs(params: Dict) -> Dict:
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


def _split_docstring(docstring: Optional[str] = None) -> Tuple[str, str, str]:
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
    args: Dict[str, str] = {}
    for line in args_section.splitlines():
        k, v = line.split(':', 1)
        args.setdefault(k.strip(), v.strip())

    return '\n'.join([f'    {k}: {v}' for k, v in args.items()])


def dynamodb_template(
    region_name: Optional[str] = None,
    api_version: Optional[str] = None,
    use_ssl: bool = True,
    verify: Union[bool, str] = True,
    endpoint_url: Optional[str] = None,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    aws_session_token: Optional[str] = None,
    config: 'Config' = None,
):
    """Template function for :py:meth:`boto3.session.Session.resource`

    Args:
        region_name: The name of the region associated with the client.
        api_version: A previous API version to use instead of the latest version
        use_ssl: Whether or not to use SSL. Note that not all services support non-ssl connections.
        verify: Whether or not to verify SSL certificates. You may provide either ``False`` or a path
            to the CA cert bundle to use.
        endpoint_url: The complete URL to use for the constructed client. If this value is provided,
            then use_ssl is ignored.
        aws_access_key_id : The access key to use when creating the client.
        aws_secret_access_key: The secret key to use when creating the client.
        aws_session_token: The session token to use when creating the client.
        config: Advanced client configuration options. See `botocore config documentation
            <https://botocore.amazonaws.com/v1/documentation/api/latest/reference/config.html>`_
            for more details.
    """


def mongo_template(
    host: str = 'localhost',
    port: int = 27017,
    document_class: Type = dict,
    tz_aware: bool = False,
    connect: bool = True,
    directConnection: bool = False,
):
    """Template function for :py:class:`motor.motor_asyncio.AsyncIOMotorClient`

    Args:
        host: Server hostname, IP address, Unix domain socket path, or
            `MongoDB URI <https://docs.mongodb.com/manual/reference/connection-string/>`_
        port: Server port
        document_class: Default class to use for documents returned from queries on this client
        tz_aware: Return timezone-aware :py:class:`.datetime` objects
        connect: Immediately connecting to MongoDB in the background. Otherwise connect on the
            first operation.
        directConnection: if True, forces this client to connect directly to the specified MongoDB
            host as a standalone. If false, the client connects to the entire replica set of which
            the given MongoDB host(s) is a part.
    """


def redis_template(
    db: Union[str, int] = 0,
    password: Optional[str] = None,
    socket_timeout: Optional[float] = None,
    socket_connect_timeout: Optional[float] = None,
    socket_keepalive: bool = False,
    socket_keepalive_options: Optional[Mapping[int, Union[int, bytes]]] = None,
    socket_type: int = 0,
    retry_on_timeout: bool = False,
    encoding: str = "utf-8",
    encoding_errors: str = "strict",
    decode_responses: bool = False,
    socket_read_size: int = 65536,
    health_check_interval: float = 0,
    client_name: Optional[str] = None,
    username: Optional[str] = None,
):
    """Template function for :py:func:`redis.asyncio.from_url` (which passes kwargs to
    :py:class:`redis.asyncio.Connection`)

    Args:
        db: Redis database index to switch to when connected
        username: Username to use if Redis server instance requires authorization
        password: Password to use if Redis server instance requires authorization
        decode_responses: Enable response decoding
        encoding: Codec to use for response decoding
        socket_timeout: Timeout for a dropped connection, in seconds
        socket_connect_timeout: Timeout for a initial connection, in seconds
        retry_on_timeout: Retry when the connection times out
    """


def sqlite_template(
    timeout: float = 5.0,
    detect_types: int = 0,
    isolation_level: Optional[str] = None,
    check_same_thread: bool = True,
    factory: Optional[Type] = None,
    cached_statements: int = 100,
    uri: bool = False,
):
    """Template function to get an accurate function signature + docs (kwargs only) for the builtin
    :py:func:`sqlite3.connect`

    Args:
        timeout: Specifies how long the connection should wait for the lock to go away until raising
            an exception.
        detect_types: Can be set to any combination of ``PARSE_DECLTYPES`` and ``PARSE_COLNAMES`` to
            turn type detection on for custom types.
        isolation_level: Transaction isolation level. Use ``None`` for autocommit mode, or one of:
            ``“DEFERRED”, “IMMEDIATE”, “EXCLUSIVE”``
        check_same_thread: If True, only the creating thread may use the connection. If False, the
            returned connection may be shared across multiple threads.
        factory: Custom subclass of :py:class:`sqlite3.Connection` used to create connections
        cached_statements: The number of statements that are cached internally for the connection
        uri: Interpret database path as a URI, to allow specifying additional options
    """
