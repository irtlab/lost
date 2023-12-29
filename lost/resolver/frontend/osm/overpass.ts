import querystring from 'querystring';
import logger from '../utils/logger';
import { overpassApi } from '../config';

const debug = logger.extend('osm:overpass');


export interface OverpassResult {
    version: number;
    generator: string;
    osm3s: Record<string, any>;
    elements: Array<OSMNode | OSMWay | OSMRelation>;
}


export interface OSMElement {
    id: number;
    type: 'node' | 'way' | 'relation';
    tags?: Record<string, string>;
}


export interface OSMNode extends OSMElement {
    type: 'node';
    lat: number;
    lon: number;
}


export interface OSMWay extends OSMElement {
    type: 'way';
    nodes: number[];
}


export interface OSMRef extends OSMElement {
    ref: number;
    role: string;
}


export interface OSMRelation extends OSMElement {
    type: 'relation';
    members: OSMRef[];
}


async function queryOverpass(query: string, timeout?: number): Promise<OverpassResult> {
    const data = `[out:json]${timeout ? `[timeout:${timeout}];` : ''}${query};out meta;>;out meta;`;
    const response = await fetch(overpassApi, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: querystring.stringify({ data })
    });
    if (!response.ok) throw new Error(response.statusText);
    return await response.json();
}


export function searchOverpassForBuildings(longitude: number, latitude: number, diameter=10, timeout=25) {
    debug(`Searching OSM Overpass for buildings near @${latitude.toFixed(7)},${longitude.toFixed(7)},${diameter}`);
    return queryOverpass(`nwr(around:${diameter},${latitude},${longitude})["building"]`, timeout);
}


export async function searchOverpassById(type: string, id: string, timeout=25) {
    debug(`Searching OSM Overpass for ${type}/${id}`);
    return queryOverpass(`${type}(${id})`, timeout);
}