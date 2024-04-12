#!/usr/bin/env python3
"""
An example that fetches and caches the content of a given web page, and all links found on that page

Usage: `./precache.py <url>`

Example:
```bash
$ # Run twice and note stats before and after
$ ./precache.py https://www.nytimes.com
Found 102 links
Completed run in 6.195 seconds and cached 53.570 MB
$ ./precache.py https://www.nytimes.com
Found 102 links
Completed run in 0.436 seconds and cached 0.000 MB
```
"""

import asyncio
import re
import sys
import time
import urllib.parse
from contextlib import contextmanager
from os.path import getsize

from aiohttp_client_cache import CachedSession, SQLiteBackend

CACHE_NAME = 'precache'
DEFAULT_URL = 'https://www.nytimes.com'
HREF_PATTERN = re.compile(r'href="(.*?)"')


async def precache_page_links(parent_url):
    """Fetch and cache the content of a given web page and all links found on that page"""
    async with CachedSession(cache=SQLiteBackend()) as session:
        urls = await get_page_links(session, parent_url)

        tasks = [asyncio.create_task(cache_url(session, url)) for url in urls]
        responses = await asyncio.gather(*tasks)

    return responses


async def get_page_links(session, url):
    """Get all links found in the HTML of the given web page"""
    print(f'Finding all links on page: {url}')
    links = set()
    response = await session.get(url)
    response.raise_for_status()
    html = await response.text()

    for link in HREF_PATTERN.findall(html):
        try:
            links.add(urllib.parse.urljoin(url, link))
        except Exception as e:
            print(f'Failed to add link: {link}')
            print(e)

    print(f'Found {len(links)} links')
    return links


async def cache_url(session, url):
    try:
        return await session.get(url)
    except Exception as e:
        print(e)
        return None


def get_cache_bytes():
    """Get the current size of the cache, in bytes"""
    try:
        return getsize(f'{CACHE_NAME}.sqlite')
    except Exception:
        return 0


@contextmanager
def measure_cache():
    """Measure time elapsed and size of added cache content"""
    start_time = time.perf_counter()
    start_bytes = get_cache_bytes()
    yield

    elapsed_time = time.perf_counter() - start_time
    cached_bytes = (get_cache_bytes() - start_bytes) / 1024 / 1024
    print(f'Completed run in {elapsed_time:0.3f} seconds and cached {cached_bytes:0.3f} MB')


if __name__ == '__main__':
    parent_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    with measure_cache():
        asyncio.run(precache_page_links(parent_url))
