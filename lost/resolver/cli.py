import sys
import click
from .. import db
from .. import osm
from . import LoSTResolver, app, resolver


@click.group(help='LoST resolver')
@click.pass_context
@click.option('--db-url', '-d', envvar='DB_URL', help='PostgreSQL database URL')
@click.option('--max-con', type=int, default=16, envvar='MAX_CON', help='Maximum number of DB connections', show_default=True)
@click.option('--min-con', type=int, default=1, envvar='MIN_CON', help='Minimum number of free DB connections', show_default=True)
def main(ctx, db_url, min_con, max_con):
    if db_url is None:
        print("Error: Please configure database via --db-url or environment variable DB_URL")
        sys.exit(1)

    ctx.ensure_object(dict)
    ctx.obj['db_url'] = db_url

    try:
        db.init(db_url, min_con=min_con, max_con=max_con)
    except db.Error as e:
        print(f"Error while connecting to datababase '{db_url}': {e}")
        sys.exit(1)

osm.cli(main)
db.cli(main)

@main.command(help='Start LoST resolver')
@click.option('--port', '-p', type=int, envvar='PORT', default=5000, help='Port number to listen on', show_default=True)
@click.option('--root-server', '-r', type=str, envvar='ROOT_SERVER', help='URL of the root server')
@click.option('--ui', '-u', is_flag=True, help='Start the web UI')
def start(port, root_server, ui):
    global resolver

    resolver = LoSTResolver(db.pool, root_server)

    if ui:
        click.echo('Starting web UI')
        from . import ui

    app.config['db'] = db.pool
    app.run('0.0.0.0', port, debug=True, threaded=True)
