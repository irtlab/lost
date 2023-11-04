import sys
import click
from flask import Flask
from flask_cors import CORS
from psycopg_pool import ConnectionPool
from . import db


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


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    try:
        if ctx.invoked_subcommand is None:
            ctx.invoke(start)
    except KeyboardInterrupt:
        pass


@cli.command()
@click.option('--port', '-p', type=int, envvar='PORT', default=5000, help='Port number to listen on', show_default=True)
@click.option('--root-server', '-r', type=str, envvar='ROOT_SERVER', help='URL of the root server')
@click.option('--db-url', '-d', envvar='DB_URL', help='PostgreSQL database URL')
@click.option('--max-con', type=int, default=16, envvar='MAX_CON', help='Maximum number of DB connections', show_default=True)
@click.option('--min-con', type=int, default=1, envvar='MIN_CON', help='Minimum number of free DB connections', show_default=True)
def start(port, root_server, db_url, min_con, max_con):
    global resolver

    if db_url is None:
        print("Error: Please configure database via --db-url or environment variable DB_URL")
        sys.exit(1)

    try:
        db.init(db_url, min_con=min_con, max_con=max_con)
    except db.Error as e:
        print(f"Error while connecting to datababase '{db_url}': {e}")
        sys.exit(1)

    resolver = LoSTResolver(db.pool, root_server)

    app.config['db'] = db.pool
    app.run('0.0.0.0', port, debug=True, threaded=True)


if __name__ == '__main__':
    cli()