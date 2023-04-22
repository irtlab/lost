import sys
import click
import lxml
import json
from pygml.v3_common import GML3Encoder, maybe_swap_coordinates
import lxml.objectify
from lxml.etree import Element, SubElement
from . import GML_NAMESPACE, SRS_URN, NAMESPACE_MAP
from .client import LoSTClient
from .geometry import Point


def convert_from_geojson(data, id='geojson'):
    '''Convert a GeoJSON object to a lxml tree

    Most GeoJSON objects contains features and feature collection. A feature is
    essentially a geometry with additional metadata. This function checks if the
    GeoJSON is a Feature or a FeatureCollection and extracts just the geometry
    from the feature. If GeoJSON object is a feature collection, it must contain
    exactly one feature.
    '''
    if not isinstance(data, dict):
        raise Exception('GeoJSON input must be an object')

    if data['type'] == 'FeatureCollection':
        if len(data['features']) != 1:
            raise Exception('Only FeatureCollections with one Feature are supported')
        data = data['features'][0]

    if data['type'] == 'Feature':
        data = data['geometry']

    # We need to generate a GML with the correct namespace (GML_NAMESPACE) and
    # coordinates in the SRS_URN order since our server implementation is kind
    # of restrictive. The pygml encoder is not very configurable, unfortunately,
    # so we need to preprocess the data here and then update srsName in the
    # resulting lxml tree.

    encoder = GML3Encoder(GML_NAMESPACE, NAMESPACE_MAP, True)
    data = maybe_swap_coordinates(data, SRS_URN)
    tree = encoder.encode(data, id)
    tree.set('srsName', SRS_URN)
    return tree



@click.group()
@click.option('--server-url', '-s', default='http://localhost:5000', help='LoST server URL', show_default=True)
@click.pass_context
def seeker(ctx, server_url):
    ctx.obj = LoSTClient(server_url)


@seeker.command()
@click.pass_obj
@click.argument('service', type=str)
@click.argument('location', type=str, nargs=-1)
@click.option('--recursive/--redirect', default=True, help='Configure recursive or redirect mode', show_default=True)
@click.option('--reference/--value', default=False, help='Receive service boundary by reference or value', show_default=True)
def find_service(client: LoSTClient, service, location, recursive, reference):
    # Parse the parameter location as follows:
    #
    # 1. If we get more than one values, assume those are geographic coordinates of a point
    # 2. If we get only one value, assume it is a file and try to open it
    #   2.1 Try to read the file as XML and interpret it as GML
    #   2.2 Try to read the file as JSON and interpret it as GeoJSON

    if len(location) == 0:
        raise click.BadArgumentUsage('Missing location')
    elif len(location) == 2:
        tree = Element(f'{{{GML_NAMESPACE}}}Point', srsName=SRS_URN)
        SubElement(tree, f'{{{GML_NAMESPACE}}}pos').text = f'{location[1]} {location[0]}'
    elif len(location) == 1:
        with open(location[0], 'rb') as f:
            text = f.read()

        try:
            tree = lxml.objectify.fromstring(text)
        except lxml.etree.XMLSyntaxError as e:
            try:
                input = json.loads(text)
            except json.JSONDecodeError as e:
                raise click.BadArgumentUsage("Unknown file format (tried XML and JSON)") from e
            else:
                tree = convert_from_geojson(input)
    else:
        raise click.BadArgumentUsage("Unsupported location format")

    uris = client.findService(service, tree, recursive=recursive, reference=reference)
    click.echo('\n'.join(uris))


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