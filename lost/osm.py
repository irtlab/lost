import os
import sys
import json
import requests
import osm2geojson
from contextlib import suppress
from os.path import join, realpath, dirname

NOMINATIM_API  = 'https://nominatim.openstreetmap.org'
OVERPASS_API   = 'https://overpass-api.de/api/interpreter'
OSM_API        = 'https://www.openstreetmap.org/api/0.6'
OSM_URI_PREFIX = 'https://www.openstreetmap.org'

DATA_DIR=realpath(join(dirname(__file__), '../data'))

WORLD = {
    'United States': (148838, {
        'Alabama'              : 161950,
        'Alaska'               : 1116270,
        'Arizona'              : 162018,
        'Arkansas'             : 161646,
        'California'           : 165475,
        'Colorado'             : 161961,
        'Connecticut'          : 165794,
        'Delaware'             : 162110,
        'Florida'              : 162050,
        'Georgia'              : 161957,
        'Hawaii'               : 166563,
        'Idaho'                : 162116,
        'Illinois'             : 122586,
        'Indiana'              : 161816,
        'Iowa'                 : 161650,
        'Kansas'               : 161644,
        'Kentucky'             : 161655,
        'Louisiana'            : 224922,
        'Maine'                : 63512,
        'Maryland'             : 162112,
        'Massachusetts'        : 61315,
        'Michigan'             : 165789,
        'Minnesota'            : 165471,
        'Mississippi'          : 161943,
        'Missouri'             : 161638,
        'Montana'              : 162115,
        'Nebraska'             : 161648,
        'Nevada'               : 165473,
        'New Hampshire'        : 67213,
        'New Jersey'           : 224951,
        'New Mexico'           : 162014,
        'New York'             : 61320,
        'North Carolina'       : 224045,
        'North Dakota'         : 161653,
        'Ohio'                 : 162061,
        'Oklahoma'             : 161645,
        'Oregon'               : 165476,
        'Pennsylvania'         : 162109,
        'Rhode Island'         : 392915,
        'South Carolina'       : 224040,
        'South Dakota'         : 161652,
        'Tennessee'            : 161838,
        'Texas'                : 114690,
        'Utah'                 : 161993,
        'Vermont'              : 60759,
        'Virginia'             : 224042,
        'Washington'           : 165479,
        'West Virginia'        : 162068,
        'Wisconsin'            : 165466,
        'Wyoming'              : 161991,
        'District of Columbia' : 162069
    }),
    'Austria'     : 16239,
    'Belgium'     : 52411,
    'Bulgaria'    : 186382,
    'Croatia'     : 214885,
    'Cyprus'      : 307787,
    'Czechia'     : 51684,
    'Denmark'     : 50046,
    'Estonia'     : 79510,
    'Finland'     : 54224,
    'France'      : 2202162,
    'Germany'     : 51477,
    'Greece'      : 192307,
    'Hungary'     : 21335,
    'Ireland'     : 62273,
    'Italy'       : 365331,
    'Latvia'      : 72594,
    'Lithuania'   : 72596,
    'Luxembourg'  : 2171347,
    'Malta'       : 365307,
    'Netherlands' : 2323309,
    'Poland'      : 49715,
    'Portugal'    : 295480,
    'Romania'     : 90689,
    'Slovakia'    : 14296,
    'Slovenia'    : 218657,
    'Spain'       : 1311341,
    'Sweden'      : 52822
}


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


def fetch_from_osm(data, dir):
    os.makedirs(dir, exist_ok=True)
    for name, node in data.items():
        if isinstance(node, tuple) or isinstance(node, list):
            id, *rest = node
            children = rest[0] if len(rest) == 1 else {}
        else:
            id = node
            children = {}

        print(f"Downloading {name}...", end='')
        sys.stdout.flush()
        gjsn = osm2geojson.json2geojson(search_overpass_by_id(f'relation/{id}'))

        _, attrs = extract_boundary(gjsn)
        name = attrs['name'].lower().replace(" ", "-")
        filename = f'{name}.geojson'

        path = join(dir, filename)
        with open(path, 'wt') as f:
            f.write(json.dumps(gjsn, indent=4))
        print(f"{path}")

        if children:
            fetch_from_osm(children, join(dir, name))


if __name__ == '__main__':
    fetch_from_osm(WORLD, join(DATA_DIR, 'world'))