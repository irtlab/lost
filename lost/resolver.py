import sys
import click
import osm2geojson
from urllib.parse import urlparse
from flask import Flask
from flask_cors import CORS
from psycopg_pool import ConnectionPool
from psycopg.types.json import Jsonb
from tabulate import tabulate
from . import db
from . import osm


class LoSTResolver:
    '''LoST resolver service implementation

    This class implements a LoST resolver, i.e., a service used by applications
    (clients) to submit queries. The resolver could be running on the same host
    as the application, e.g., in the form of a background process that
    communicates with the application via an inter-process communication channel
    (DBus). It could be also provided as local network service, e.g., as part of
    cloud services provided to applications running on the cloud infrastructure.
    '''
    def __init__(self, db: ConnectionPool, root_server):
        self.db = db
        self.root_server = root_server


resolver: LoSTResolver
app = Flask(__name__)
CORS(app)


@click.group()
@click.pass_context
@click.option('--db-url', '-d', envvar='DB_URL', help='PostgreSQL database URL')
def cli(ctx, db_url):
    if db_url is None:
        print("Error: Please configure database via --db-url or environment variable DB_URL")
        sys.exit(1)

    try:
        db.init(db_url)
    except db.Error as e:
        print(f"Error while connecting to datababase '{db_url}': {e}")
        sys.exit(1)

    ctx.ensure_object(dict)
    ctx.obj['db_url'] = db_url


@cli.command()
@click.option('--port', '-p', type=int, envvar='PORT', default=5000, help='Port number to listen on', show_default=True)
@click.option('--root-server', '-r', type=str, envvar='ROOT_SERVER', help='URL of the root server')
@click.option('--max-con', type=int, default=16, envvar='MAX_CON', help='Maximum number of DB connections', show_default=True)
@click.option('--min-con', type=int, default=1, envvar='MIN_CON', help='Minimum number of free DB connections', show_default=True)
def start(port, root_server, db_url, min_con, max_con):
    global resolver

    resolver = LoSTResolver(db.pool, root_server)

    app.config['db'] = db.pool
    app.run('0.0.0.0', port, debug=True, threaded=True)


@cli.group(invoke_without_command=True)
@click.pass_context
def shape(ctx):
    if ctx.invoked_subcommand is None:
        ctx.invoke(list)


@shape.command()
@click.argument('url', type=str)
@click.option('--name', '-n', help='Override name attribute')
def fetch(url, name):
    parsed = urlparse(url, allow_fragments=False)
    if parsed.hostname is None or not parsed.hostname.endswith('openstreetmap.org'):
        click.echo(f'Unsupported URL {url}', err=True)
        sys.exit(1)

    print(f"Downloading {url}...", end='')
    sys.stdout.flush()
    jsn = osm.search_overpass_by_id(parsed.path[1:])
    gjsn = osm2geojson.json2geojson(jsn)

    geometry, attrs = osm.extract_boundary(gjsn)
    print("done.")

    if name is not None:
        attrs['name'] = name

    with db.pool.connection() as con:
        con.execute('''
            INSERT INTO shape
                (uri, geometries, modified, attrs)
            VALUES (
                %s,
                ST_ForceCollection(ST_GeomFromGeoJSON(%s)),
                %s,
                %s)
            ON CONFLICT(uri)
            DO
                UPDATE SET
                    geometries=EXCLUDED.geometries,
                    modified=EXCLUDED.modified,
                    attrs=EXCLUDED.attrs
        ''', (url, Jsonb(geometry), attrs['timestamp'], Jsonb(attrs)))


@shape.command()
@click.pass_context
def fetch_us(ctx):
    from .osm import US_MAP
    for id in US_MAP.values():
        ctx.invoke(fetch, url=f'https://www.openstreetmap.org/{id}', name=None)


@shape.command()
@click.option('--attrs', '-a', is_flag=True, help='Show attributes')
def list(attrs):
    headers = ['Name', 'URI', 'Created', 'Modified']
    if attrs:
        headers.append('Attributes')

    with db.pool.connection() as con:
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


@shape.command()
@click.argument('uri', type=str)
def delete(uri):
    with db.pool.connection() as con:
            con.execute('''
                DELETE FROM shape
                WHERE uri=%s
            ''', (uri,))


if __name__ == '__main__':
    cli()