import atexit
import psycopg
from .guid import GUID
from psycopg.adapt import Loader, Dumper
from psycopg_pool import ConnectionPool


# Create a pool of persistent PostgreSQL database connections. When we are done
# with a PostgreSQL connection, we simply return it to the pool without closing
# the connection. This helps avoid the need to open a new database connection
# for every request.
pool: ConnectionPool = None


def adapt_for_guid(con: psycopg.Connection):
    class GUIDLoader(Loader):
        def load(self, data):
            return GUID(str(data, 'ascii'))

    class GUIDDumper(Dumper):
        oid = psycopg.adapters.types["uuid"].oid

        def dump(self, data):
            return f"{data.value}".encode('ascii')

    con.adapters.register_loader('uuid', GUIDLoader)
    con.adapters.register_dumper(GUID, GUIDDumper)


def init(db_url: str, min_con=1, max_con=16):
    global pool

    if pool is not None:
        raise Exception('Database is already initialized')

    pool = ConnectionPool(db_url, min_size=min_con, max_size=max_con, num_workers=1, kwargs={
        'autocommit': True
    }, configure=adapt_for_guid)
    atexit.register(lambda: pool.close())
    # Wait for the connection pool to create its first connections. We want
    # to fail early if the database cannot be connected for some reason.
    pool.wait()
