import atexit
import psycopg
import sys
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


def cli(parent):
    import click
    from tabulate import tabulate


    @parent.group(help='Commands for working with shapes', invoke_without_command=True)
    @click.pass_context
    def shape(ctx):
        if ctx.invoked_subcommand is None:
            ctx.invoke(list)


    @shape.command(help='List shapes in the local database')
    @click.option('--attrs', '-a', is_flag=True, help='Show attributes')
    def list(attrs):
        headers = ['Name', 'URI', 'Created', 'Modified']
        if attrs:
            headers.append('Attributes')

        with pool.connection() as con:
            with con.cursor() as cur:
                cur.execute('''
                    SELECT uri, created, modified, attrs
                    FROM shape
                ''')

                data = []
                for row in cur.fetchall():
                    r = [row[3]['name'], row[0], row[1].strftime('%c'), row[2].strftime('%c')]
                    if attrs:
                        r.append(row[3])
                    data.append(r)

                click.echo(tabulate(data, tablefmt="psql", headers=headers))


    @shape.command(help='Retrieve shape in GeoJSON format')
    @click.argument('uri', type=str)
    def get(uri):
        with pool.connection() as con:
            cur = con.execute('''
                SELECT ST_AsGeoJSON(geometries) FROM shape
                WHERE uri=%s
            ''', (uri,))
            row = cur.fetchone()
            if row is None:
                raise click.Abort('Not found')
            click.echo(row[0])


    @shape.command(help='Remove a shape from the local database')
    @click.argument('uri', type=str)
    def delete(uri):
        with pool.connection() as con:
            con.execute('''
                DELETE FROM shape
                WHERE uri=%s
            ''', (uri,))
