import querystring from 'querystring';
import logger from '../utils/logger';
import { Coordinates } from '../utils/coordinates';
import { nominatimApi } from '../config';

const debug = logger.extend('osm:geocode');


interface NominatimData {
    place_id: number;
    license: string;
    osm_type: string;
    osm_id: number;
    place_rank: number;
    category: string;
    type: string;
    addresstype: string;
    name: string | null;
    address: Record<string, string>;
    display_name: string;
    importance: number;
    lat: string;
    lon: string;
    boundingbox: string[];
}


interface NominatimError {
    error: string;
}

type NominatimResult = NominatimData[] | NominatimError;
type ReverseNominatimResult = NominatimData | NominatimError;


export interface GeocodeResult extends Omit<NominatimData, 'lat'|'lon'|'boundingbox'> {
    lat: number,
    lon: number,
    boundingbox: number[]
}


function parseNominatimData(v: NominatimData): GeocodeResult {
    const { lat, lon, boundingbox, ...rest } = v;
    const lat_ = parseFloat(lat);
    const lon_ = parseFloat(lon);
    const bb = boundingbox.map(v => parseFloat(v));

    if (Number.isNaN(lat_) || Number.isNaN(lon_))
        throw new Error('Invalid latitude or longitude value');

    bb.forEach(v => {
        if (Number.isNaN(v)) throw new Error('Invalid bounding box value');
    });

    return {
        lat: lat_,
        lon: lon_,
        boundingbox: bb,
        ...rest
    };
}


export async function geocode(query: string): Promise<GeocodeResult[]> {
    debug(`Searching OSM Nominativ for '${query}'`);
    const qs = querystring.stringify({ format: 'jsonv2' });
    const response = await fetch(`${nominatimApi}/search/${query}?${qs}`);
    if (!response.ok) throw new Error(response.statusText);

    const data = await response.json() as NominatimResult;
    if (!Array.isArray(data))
        throw new Error(data.error);

    // Sort the array in a decreasing importance order
    data.sort((a, b) => b.importance - a.importance);
    return data.map(parseNominatimData);
}


export async function reverseGeocode(coords: Coordinates): Promise<GeocodeResult> {
    debug(`Doing reverse OSM Nominativ lookup for '@${coords[1]},${coords[0]}'`);
    const qs = querystring.stringify({
        format : 'jsonv2',
        lon    : coords[0],
        lat    : coords[1]
    });
    const response = await fetch(`${nominatimApi}/reverse?${qs}`);
    if (!response.ok) throw new Error(response.statusText);

    const data = await response.json() as ReverseNominatimResult;
    if ('error' in data)
        throw new Error(data.error);

    return parseNominatimData(data);
}
