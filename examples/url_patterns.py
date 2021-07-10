#!/usr/bin/env python3
# fmt: off
"""
An example of setting expiration based on {ref}`user_guide:url patterns`
"""
import asyncio
from datetime import timedelta

from aiohttp_client_cache import CachedSession, SQLiteBackend

default_expire_after = 60 * 60               # By default, cached responses expire in an hour
urls_expire_after = {
    'httpbin.org/image': timedelta(days=7),  # Requests for this base URL will expire in a week
    '*.fillmurray.com': -1,                  # Requests matching this pattern will never expire
}
urls = [
    'https://httpbin.org/get',               # Will expire in an hour
    'https://httpbin.org/image/jpeg',        # Will expire in a week
    'http://www.fillmurray.com/460/300',     # Will never expire
]


async def main():
    cache = SQLiteBackend(
        cache_name='~/.cache/aiohttp-requests.db',
        expire_after=default_expire_after,
        urls_expire_after=urls_expire_after,
    )

    async with CachedSession(cache=cache) as session:
        tasks = [asyncio.create_task(session.get(url)) for url in urls]
        return await asyncio.gather(*tasks)


if __name__ == "__main__":
    original_responses = asyncio.run(main())
    cached_responses = asyncio.run(main())
    for response in cached_responses:
        expires = response.expires.isoformat() if response.expires else 'Never'
        print(f'{response.url}: {expires}')
