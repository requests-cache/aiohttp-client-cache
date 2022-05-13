"""Template functions to supplement docs with accurate details for backend connection functions:

* Function signatures
* Type annotations
* Argument docs
"""
from typing import TYPE_CHECKING, Mapping, Optional, Type, Union

if TYPE_CHECKING:
    from botocore.client import Config


def dynamodb_template(
    region_name: str = None,
    api_version: str = None,
    use_ssl: bool = True,
    verify: Union[bool, str] = None,
    endpoint_url: str = None,
    aws_access_key_id: str = None,
    aws_secret_access_key: str = None,
    aws_session_token: str = None,
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
    isolation_level: str = None,
    check_same_thread: bool = True,
    factory: Type = None,
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
