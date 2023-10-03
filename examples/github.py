#!/usr/bin/env python3
# fmt: off
"""
An example of making conditional request to the GitHub Rest API`
"""
import asyncio

from aiohttp_client_cache import CachedSession, FileBackend

CACHE_DIR = "~/.cache/aiohttp-requests"


async def main():
    cache = FileBackend(cache_name=CACHE_DIR)
    await cache.clear()

    org = "requests-cache"
    url = f"https://api.github.com/orgs/{org}/repos"

    async with CachedSession(cache=cache) as session:
        response = await session.get(url)
        print(f"url = {response.url}, status = {response.status}, "
              f"ratelimit-used = {response.headers['x-ratelimit-used']}")

        response = await session.get(url, refresh=True)
        print(f"url = {response.url}, status = {response.status}, "
              f"ratelimit-used = {response.headers['x-ratelimit-used']}")


if __name__ == "__main__":
    asyncio.run(main())
