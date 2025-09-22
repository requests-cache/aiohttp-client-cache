from __future__ import annotations

import pytest

from aiohttp_client_cache.backends.postgresql import PostgresBackend, PostgresCache
from test.integration import BaseBackendTest, BaseStorageTest

pytestmark = pytest.mark.asyncio

TEST_DATABASE_URL = 'postgresql://postgres:postgres@localhost:5433/aiohttp_cache'


class TestPostgresCache(BaseStorageTest):
    picklable = True
    storage_class = PostgresCache
    init_kwargs = {'database_url': TEST_DATABASE_URL}


class TestPostgresBackend(BaseBackendTest):
    backend_class = PostgresBackend
    init_kwargs = {'database_url': TEST_DATABASE_URL}
