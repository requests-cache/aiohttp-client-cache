#!/usr/bin/env python3
"""
An example of testing the cache to prove that it's not making more requests than expected.
"""

import asyncio
from contextlib import asynccontextmanager
from logging import basicConfig, getLogger
from unittest.mock import patch

from aiohttp import ClientSession

from aiohttp_client_cache import CachedResponse, CachedSession, SQLiteBackend

basicConfig(level='INFO')
logger = getLogger('aiohttp_client_cache.examples')
# Uncomment for more verbose debug output
# getLogger('aiohttp_client_cache').setLevel('DEBUG')


@asynccontextmanager
async def log_requests():
    """Context manager that mocks and logs all non-cached requests"""

    async def mock_response(*args, **kwargs):
        return CachedResponse(method='GET', reason='OK', status=200, url='url', version='1.1')

    with patch.object(ClientSession, '_request', side_effect=mock_response) as mock_request:
        async with CachedSession(cache=SQLiteBackend('cache-test.sqlite')) as session:
            await session.cache.clear()
            yield session
            cached_responses = [v async for v in session.cache.responses.values()]

    logger.debug('All calls to ClientSession._request():')
    logger.debug(mock_request.mock_calls)

    logger.info(f'Responses cached: {len(cached_responses)}')
    logger.info(f'Requests sent: {mock_request.call_count}')


async def main():
    """Example usage; replace with any other requests you want to test"""
    async with log_requests() as session:
        for i in range(10):
            response = await session.get('http://httpbin.org/get')
            logger.debug(f'Response {i}: {type(response).__name__}')


if __name__ == '__main__':
    asyncio.run(main())
