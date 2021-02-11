# TODO
import pytest

from aiohttp_client_cache import CachedSession


@pytest.mark.asyncio
async def test_session():
    CachedSession()
