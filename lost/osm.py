import sys
import json
import requests
import osm2geojson
from contextlib import suppress
from os.path import join, realpath, dirname

NOMINATIM_API = 'https://nominatim.openstreetmap.org'
OVERPASS_API = 'https://overpass-api.de/api/interpreter'


US_MAP = {
    'US'                   : 'relation/148838',
    'Alabama'              : 'relation/161950',
    'Alaska'               : 'relation/1116270',
    'Arizona'              : 'relation/162018',
    'Arkansas'             : 'relation/161646',
    'California'           : 'relation/165475',
    'Colorado'             : 'relation/161961',
    'Connecticut'          : 'relation/165794',
    'Delaware'             : 'relation/162110',
    'Florida'              : 'relation/162050',
    'Georgia'              : 'relation/161957',
    'Hawaii'               : 'relation/166563',
    'Idaho'                : 'relation/162116',
    'Illinois'             : 'relation/122586',
    'Indiana'              : 'relation/161816',
    'Iowa'                 : 'relation/161650',
    'Kansas'               : 'relation/161644',
    'Kentucky'             : 'relation/161655',
    'Louisiana'            : 'relation/224922',
    'Maine'                : 'relation/63512',
    'Maryland'             : 'relation/162112',
    'Massachusetts'        : 'relation/61315',
    'Michigan'             : 'relation/165789',
    'Minnesota'            : 'relation/165471',
    'Mississippi'          : 'relation/161943',
    'Missouri'             : 'relation/161638',
    'Montana'              : 'relation/162115',
    'Nebraska'             : 'relation/161648',
    'Nevada'               : 'relation/165473',
    'New Hampshire'        : 'relation/67213',
    'New Jersey'           : 'relation/224951',
    'New Mexico'           : 'relation/162014',
    'New York'             : 'relation/61320',
    'North Carolina'       : 'relation/224045',
    'North Dakota'         : 'relation/161653',
    'Ohio'                 : 'relation/162061',
    'Oklahoma'             : 'relation/161645',
    'Oregon'               : 'relation/165476',
    'Pennsylvania'         : 'relation/162109',
    'Rhode Island'         : 'relation/392915',
    'South Carolina'       : 'relation/224040',
    'South Dakota'         : 'relation/161652',
    'Tennessee'            : 'relation/161838',
    'Texas'                : 'relation/114690',
    'Utah'                 : 'relation/161993',
    'Vermont'              : 'relation/60759',
    'Virginia'             : 'relation/224042',
    'Washington'           : 'relation/165479',
    'West Virginia'        : 'relation/162068',
    'Wisconsin'            : 'relation/165466',
    'Wyoming'              : 'relation/161991',
    'District of Columbia' : 'relation/162069'
}


def query_overpass(query: str, timeout: float | None):
    timespec = f'[timeout:{timeout}];' if timeout is not None else ''
    data = f'[out:json]{timespec}{query};out meta;>;out meta;'

    res = requests.post(OVERPASS_API, data={'data': data}, headers={
        'Content-Type': 'application/x-www-form-urlencoded'
    })

    res.raise_for_status()
    return res.json()


def search_overpass_by_id(id: str, timeout=25):
    type_, id = id.split('/')
    return query_overpass(f'{type_}({id})', timeout)


def download_us_map(dir=realpath(join(dirname(__file__), '../data/us'))):
    for key, id in US_MAP.items():
        name = key.lower().replace(' ', '-')

        pathname = f'{join(dir, name)}.geojson'
        with open(pathname, 'wt') as f:
            print(f"Downloading {key} boundary to {pathname}...", end='')
            sys.stdout.flush()

            jsn = search_overpass_by_id(id)
            gjsn = osm2geojson.json2geojson(jsn)
            f.write(json.dumps(gjsn, indent=4))

            print("done.")


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
        with suppress(KeyError): attrs['name'] = tags['name']

        return feature['geometry'], attrs

    raise Exception('No Feature with type relation found')


if __name__ == '__main__':
    download_us_map()