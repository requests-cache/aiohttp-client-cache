from .base import BaseCache
from .storage.dbdict import DbDict, DbPickleDict


class DbCache(BaseCache):
    """sqlite cache backend.

    Reading is fast, saving is a bit slower. It can store a large amount of data
    with low memory usage.
    """

    def __init__(
        self, cache_name: str, *args, fast_save: bool = False, extension: str = '.sqlite', **kwargs
    ):
        """
        Args:
            location: database filename prefix
            fast_save: Speedup cache saving up to 50 times but with possibility of data loss.
                See :py:class:`.backends.DbDict` for more info
            extension: Database file extension
        """
        super().__init__(cache_name, *args, **kwargs)
        self.responses = DbPickleDict(cache_name + extension, 'responses', fast_save=fast_save)
        self.keys_map = DbDict(cache_name + extension, 'urls')
