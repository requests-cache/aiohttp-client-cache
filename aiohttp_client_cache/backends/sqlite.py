from collections.abc import MutableMapping
from contextlib import contextmanager
import pickle
import sqlite3
import threading

from aiohttp_client_cache.backends import PICKLE_PROTOCOL, BaseCache


class DbCache(BaseCache):
    """SQLite cache backend.

    Reading is fast, saving is a bit slower. It can store a large amount of data
    with low memory usage.
    """

    def __init__(
        self, cache_name: str, *args, fast_save: bool = False, extension: str = '.sqlite', **kwargs
    ):
        """
        Args:
            cache_name: database filename prefix
            fast_save: Speedup cache saving up to 50 times but with possibility of data loss.
                See :py:class:`.backends.DbDict` for more info
            extension: Database file extension
        """
        super().__init__(cache_name, *args, **kwargs)
        self.responses = DbPickleDict(cache_name + extension, 'responses', fast_save=fast_save)
        self.keys_map = DbDict(cache_name + extension, 'urls')


class DbDict(MutableMapping):
    """A dictionary-like object for saving large datasets to `sqlite` database

    It's possible to create multiply DbDict instances, which will be stored as separate
    tables in one database::

        d1 = DbDict('test', 'table1')
        d2 = DbDict('test', 'table2')
        d3 = DbDict('test', 'table3')

    all data will be stored in ``test.sqlite`` database into
    correspondent tables: ``table1``, ``table2`` and ``table3``
    """

    def __init__(self, filename, table_name: str, fast_save=False):
        """
        Args:
            filename: filename for database (without extension)
            table_name: table name
            fast_save: If it's True, then sqlite will be configured with
                          `'PRAGMA synchronous = 0;' <http://www.sqlite.org/pragma.html#pragma_synchronous>`_
                          to speedup cache saving, but be careful, it's dangerous.
                          Tests showed that insertion order of records can be wrong with this option.
        """
        self.filename = filename
        self.table_name = table_name
        self.fast_save = fast_save

        #: Transactions can be committed if this property is set to `True`
        self.can_commit = True

        self._bulk_commit = False
        self._pending_connection = None
        self._lock = threading.RLock()
        with self.connection() as con:
            con.execute(f'create table if not exists `{self.table_name}` (key PRIMARY KEY, value)')

    @contextmanager
    def connection(self, commit_on_success=False):
        with self._lock:
            if self._bulk_commit:
                if self._pending_connection is None:
                    self._pending_connection = sqlite3.connect(self.filename)
                con = self._pending_connection
            else:
                con = sqlite3.connect(self.filename)
            try:
                if self.fast_save:
                    con.execute('PRAGMA synchronous = 0;')
                yield con
                if commit_on_success and self.can_commit:
                    con.commit()
            finally:
                if not self._bulk_commit:
                    con.close()

    def commit(self, force=False):
        """
        Commits pending transaction if :attr:`can_commit` or `force` is `True`

        :param force: force commit, ignore :attr:`can_commit`
        """
        if force or self.can_commit:
            if self._pending_connection is not None:
                self._pending_connection.commit()

    @contextmanager
    def bulk_commit(self):
        """
        Context manager used to speedup insertion of big number of records
        ::

            >>> d1 = DbDict('test')
            >>> with d1.bulk_commit():
            ...     for i in range(1000):
            ...         d1[i] = i * 2

        """
        self._bulk_commit = True
        self.can_commit = False
        try:
            yield
            self.commit(True)
        finally:
            self._bulk_commit = False
            self.can_commit = True
            if self._pending_connection is not None:
                self._pending_connection.close()
                self._pending_connection = None

    def get_all(self):
        with self.connection() as con:
            return con.execute(f'select value from `{self.table_name}`').fetchall()

    def __getitem__(self, key):
        with self.connection() as con:
            row = con.execute(
                f'select value from `{self.table_name}` where key=?', (key,)
            ).fetchone()
            if not row:
                raise KeyError
            return row[0]

    def __setitem__(self, key, item):
        with self.connection(True) as con:
            con.execute(
                f'insert or replace into `{self.table_name}` (key,value) values (?,?)',
                (key, item),
            )

    def __delitem__(self, key):
        with self.connection(True) as con:
            cur = con.execute(f'delete from `{self.table_name}` where key=?', (key,))
            if not cur.rowcount:
                raise KeyError

    def __iter__(self):
        with self.connection() as con:
            for row in con.execute(f'select key from `{self.table_name}`'):
                yield row[0]

    def __len__(self):
        with self.connection() as con:
            return con.execute(f'select count(key) from `{self.table_name}`').fetchone()[0]

    def clear(self):
        with self.connection(True) as con:
            con.execute(f'drop table `{self.table_name}`')
            con.execute(f'create table `{self.table_name}` (key PRIMARY KEY, value)')
            con.execute('vacuum')

    def __str__(self):
        return str(dict(self.items()))


class DbPickleDict(DbDict):
    """ Same as :class:`DbDict`, but pickles values before saving """

    def __setitem__(self, key, item):
        super().__setitem__(key, sqlite3.Binary(pickle.dumps(item, protocol=PICKLE_PROTOCOL)))

    def __getitem__(self, key):
        return pickle.loads(bytes(super().__getitem__(key)))
