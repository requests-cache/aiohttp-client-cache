from logging import basicConfig, getLogger

# Configure logging for pytest session
basicConfig(level='INFO')
getLogger('aiohttp_client_cache').setLevel('DEBUG')
