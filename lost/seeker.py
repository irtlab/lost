import sys
import click
from .client import LoSTClient
from .geometry import Point


@click.group()
@click.option('--server-url', '-s', default='http://localhost:5000', help='LoST server URL', show_default=True)
@click.pass_context
def seeker(ctx, server_url):
    ctx.obj = LoSTClient(server_url)


@seeker.command()
@click.pass_obj
@click.argument('service', type=str)
@click.argument('longitude', type=float)
@click.argument('latitude', type=float)
def find_service(client: LoSTClient, service, longitude, latitude):
    uri = client.findService(service, Point(longitude, latitude))
    click.echo('\n'.join(uri))


@seeker.command()
@click.pass_obj
def get_service_boundary(client: LoSTClient):
    pass


@seeker.command()
@click.option('--by-location', '-l', is_flag=True, default=False)
@click.pass_obj
def list_services(client: LoSTClient, by_location):
    pass


def cli():
    try:
        seeker()
    except Exception as e:
        click.echo(f'Error: {e}')
        sys.exit(1)


if __name__ == '__main__':
    cli()