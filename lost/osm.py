import sys
import requests
import osm2geojson
from contextlib import suppress
from psycopg.types.json import Jsonb
from . import db


NOMINATIM_API  = 'https://nominatim.openstreetmap.org'
OVERPASS_API   = 'https://overpass-api.de/api/interpreter'
OSM_API        = 'https://www.openstreetmap.org/api/0.6'
OSM_URI_PREFIX = 'https://www.openstreetmap.org'


def query_overpass(query: str, timeout: float | None):
    timespec = f'[timeout:{timeout}];' if timeout is not None else ''
    data = f'[out:json]{timespec}{query};out meta;>;out meta;'

    res = requests.post(OVERPASS_API, data={'data': data}, headers={
        'Content-Type': 'application/x-www-form-urlencoded'
    })

    res.raise_for_status()
    return res.json()


def fetch_osm_xml(id: str):
    res = requests.get(f'{OSM_API}/{id}')
    res.raise_for_status()
    return res.text


def search_overpass_by_id(id: str, timeout=25):
    type_, id = id.split('/')
    return query_overpass(f'{type_}({id})', timeout)


def extract_boundary(obj: dict):
    if obj['type'] != 'FeatureCollection':
        raise Exception('FeatureCollection expected')
    
    for feature in obj['features']:
        if feature['type'] != 'Feature': continue

        props = feature['properties']
        tags = props['tags']

        if props['type'] != "relation" and props['type'] != "way":
            continue

        attrs = dict()
        attrs['id'] = props['id']
        attrs['timestamp'] = props['timestamp']

        with suppress(KeyError): attrs['country'] = tags['ISO3166-1']
        with suppress(KeyError): attrs['state'] = tags['ISO3166-2']

        try:
            attrs['name'] = tags['name:en']
        except KeyError:
            with suppress(KeyError):
                attrs['name'] = tags['name']

        return feature['geometry'], attrs

    raise Exception('No Feature with type relation found')


def cli(parent):
    import click
    from urllib.parse import urlparse

    @parent.group(help='Commands for working with OpenStreetMap')
    def osm():
        pass

    @osm.command(help='Fetch geographic object from OpenStreetMap')
    @click.argument('url', type=str)
    @click.option('--name', '-n', help='Override name attribute')
    def fetch(url, name):
        parsed = urlparse(url, allow_fragments=False)
        if parsed.hostname is None or not parsed.hostname.endswith('openstreetmap.org'):
            click.echo(f'Unsupported URL {url}', err=True)
            sys.exit(1)

        print(f"Downloading {url}...", end='')
        sys.stdout.flush()
        jsn = search_overpass_by_id(parsed.path[1:])
        gjsn = osm2geojson.json2geojson(jsn)

        geometry, attrs = extract_boundary(gjsn)
        print("done.")

        if name is not None:
            attrs['name'] = name

        with db.pool.connection() as con:
            con.execute('''
                INSERT INTO shape
                    (uri, geometries, updated, attrs)
                VALUES (
                    %s,
                    ST_ForceCollection(ST_GeomFromGeoJSON(%s)),
                    %s,
                    %s)
                ON CONFLICT(uri)
                DO
                    UPDATE SET
                        geometries=EXCLUDED.geometries,
                        updated=EXCLUDED.updated,
                        attrs=EXCLUDED.attrs
            ''', (url, Jsonb(geometry), attrs['timestamp'], Jsonb(attrs)))
