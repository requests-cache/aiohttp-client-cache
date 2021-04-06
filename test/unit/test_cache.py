"""Tests for behavior across CachedSession, backend classes, and storage classes"""
import pickle
import pytest
from uuid import uuid4

from itsdangerous.exc import BadSignature
from itsdangerous.serializer import Serializer

from aiohttp_client_cache import CachedSession, SQLiteBackend
from test.conftest import tempfile_session

pytestmark = [pytest.mark.asyncio]


async def test_serializer_pickle():
    """Without a secret key, plain pickle should be used"""
    session = CachedSession()
    assert session.cache.responses._serializer == pickle


async def test_serializer_itsdangerous():
    """With a secret key, itsdangerous should be used"""
    secret_key = str(uuid4())
    with tempfile_session(secret_key=secret_key) as session:
        assert isinstance(session.cache.responses._serializer, Serializer)

        # Simple serialize/deserialize round trip
        await session.cache.responses.write('key', 'value')
        assert (await session.cache.responses.read('key')) == 'value'

        # Without the same signing key, the item shouldn't be considered safe to deserialize
        cache = SQLiteBackend(cache_name=session.cache.name, secret_key='a different key')
        session_2 = CachedSession(cache=cache)
        with pytest.raises(BadSignature):
            await session_2.cache.responses.read('key')
