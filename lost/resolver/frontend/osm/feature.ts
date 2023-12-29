import inside from '@turf/boolean-point-in-polygon';
import debug from 'debug';
import osmtogeojson from 'osmtogeojson';
import { Feature as GeoJSONFeature } from '../utils/geojson';
import { geocode, reverseGeocode } from './geocode';
import { OverpassResult, searchOverpassById, searchOverpassForBuildings } from './overpass';


export async function searchOpenStreetMap(query: string, doReverseGeocode = true) {
    let dia = 100;
    let lat: number | undefined, lng: number | undefined;
    let id: string | undefined;

    let result: OverpassResult;
    if (query.startsWith('https://www.openstreetmap.org/')) {
        const comps = query.split('/');
        const type = comps[3];
        const num = comps[4];
        switch(type) {
            case 'node'     : break;
            case 'way'      : break;
            case 'relation' : break;
            default         : throw new Error(`Unsupported OSM type '${type}'`);
        }

        if (num.length === 0)
            throw new Error(`Missing OSM object id`);

        id = `${type}/${num}`;
        result = await searchOverpassById(type, num);
    } else {
        if (query.startsWith('@')) {
            let ll = query.slice(1).split(',');
            if (ll.length !== 2 && ll.length !== 3) {
                ll = query.slice(1).split('/');
                if (ll.length !== 2 && ll.length !== 3)
                    throw new Error(`Invalid longitude/latitude format. Expected: '@latitude,longitude,[diameter]' `);
            }

            lng = Number(ll[1]);
            lat = Number(ll[0]);
            if (ll.length === 3) dia = Number(ll[2]);

            if (Number.isNaN(lng)) throw new Error(`Invalind longitude value: ${ll[1]}`);
            if (Number.isNaN(lat)) throw new Error(`Invalid latitude value: ${ll[0]}`);
            if (Number.isNaN(dia)) throw new Error(`Invalid diameter value: ${ll[2]}`);
        } else {
            const res = await geocode(query);
            if (res.length === 0) throw new Error(`No results for query '${query}'.`);
            else if (res.length > 1) throw new Error(`Multiple results for query '${query}', please refine your search.`);

            lng = res[0].lon;
            lat = res[0].lat;
        }

        result = await searchOverpassForBuildings(lng, lat, dia);
    }

    const geojson = osmtogeojson(result);

    if (geojson.features.length === 0) {
        throw new Error(`Couldn't match '${query}' to any feature.`);
    }

    let feature;

    if (lng !== undefined && lat !== undefined) {
        // If we got multiple building candidates, we need to find the one that
        // contains our node's longitude,latitude.
        for(const f of geojson.features)
            if (inside([lng, lat], f as any)) {
                feature = f;
                break;
            }
    } else if (id !== undefined) {
        for(const f of geojson.features)
            if (f.id === id ) {
                feature = f;
                break;
            }
    }

    if (feature === undefined) {
        if (geojson.features.length !== 1)
            throw new Error(`Query ${query} returned too many features`);
        feature = geojson.features[0];
    }

    if (lng !== undefined && lat !== undefined && doReverseGeocode) {
        // Do a reverse geocoding lookup on the centroid of the found GeoJSON
        // feature and if a result is found, merge its selected attributes into the
        // feature's properties.
        try {
            // FIXME: Check if the function center really works correctly. It
            // seems to return points outside of the polygon.
            //
            // Ideally, use the coordinates obtained from geocoding. If there
            // are no such coordinates, calculate the centroid and uset that.
            //
            // FIXME: Maybe also merge the attributes obtained through the
            // geocoding lookup above.
            //
            //const { geometry: { coordinates } } = center(geojson as any);
            const data = await reverseGeocode([ lng, lat ]);
            const p = feature.properties = feature.properties || {};

            if (!p.category)     p.category = data.category;
            if (!p.addresstype)  p.addresstype = data.addresstype;
            if (!p.name)         p.name = data.name;
            if (!p.address)      p.address = {...data.address};
            if (!p.display_name) p.display_name = data.display_name;
        } catch(error) {
            debug(`Ignoring reverseGeocode error: ${error}`);
        }
    }

    return feature;
}


export function getFeatureName({ properties: p = {} }: { properties?: Record<string, any> | null}) {
    if (!p) return null;
    return p.name || p.alt_name || p.display_name || null;
}


export function guessFeatureType(feature: GeoJSONFeature) {
    const { properties, geometry } = feature;
    if (properties !== null && properties !== undefined) {
        if ('highway' in properties) return 'Way';
        if ('building' in properties) return 'Building';
    }

    if (geometry.type === 'Point' || geometry.type === 'MultiPoint')
        return 'Point';

    if (geometry.type === 'LineString' || geometry.type === 'MultiLineString')
        return 'Way';

    if (geometry.type === 'Polygon' || geometry.type === 'MultiPolygon')
        return 'Area';

    throw new Error('Cannot guess the type of OpenStreetMap feature');
}
