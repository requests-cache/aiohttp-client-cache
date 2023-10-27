#!/usr/bin/env python3
# fmt: off
"""
An example of making conditional requests to the GitHub Rest API`
"""

import asyncio
import logging

from aiohttp_client_cache import CachedSession, FileBackend

CACHE_DIR = "~/.cache/aiohttp-requests"


async def main():
    cache = FileBackend(cache_name=CACHE_DIR, use_temp=True)
    await cache.clear()

    org = "requests-cache"
    url = f"https://api.github.com/orgs/{org}/repos"

    # we make 2 requests for the same resource (list of all repos of the requests-cache organization)
    # the second request refreshes the cached response with the remote server
    # the debug output should illustrate that the cached response gets refreshed
    async with CachedSession(cache=cache) as session:
        response = await session.get(url)
        print(f"url = {response.url}, status = {response.status}, "
              f"ratelimit-used = {response.headers['x-ratelimit-used']}")

        await asyncio.sleep(1)

        response = await session.get(url, refresh=True)
        print(f"url = {response.url}, status = {response.status}, "
              f"ratelimit-used = {response.headers['x-ratelimit-used']}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("aiohttp_client_cache").setLevel(logging.DEBUG)
    asyncio.run(main())
