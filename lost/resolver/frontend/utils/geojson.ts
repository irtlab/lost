import proj4 from 'proj4';
import { Coordinates } from './coordinates';

type BoundingBox = [number, number, number, number];

export type PrimitiveGeometryType = 'Point' | 'LineString' | 'Polygon';
export type MultiGeometryType = PrimitiveGeometryType | 'MultiPoint' | 'MultiLineString' | 'MultiPolygon';
export type GeometryType = MultiGeometryType | 'GeometryCollection';

type GeoJSONType = GeometryType | 'Feature' | 'FeatureCollection';

// According to the GeoJSON specification, the bbox property can be present on a
// Geometry objects iff the object is the top level GeoJSON object. That is
// difficult to express in TypeScript since an interface cannot extend a union
// type, so we add an optional bbox property on individual geometry objects
// instead.

interface Base {
    id?: string | number;
    type: GeoJSONType;
    bbox?: BoundingBox;
    crs?: CRS;
}

interface CRS {
    type: 'name',
    properties: {
        name: string;
    }
}

interface Point extends Base {
    type: 'Point';
    coordinates: Coordinates;
}

interface MultiPoint extends Base {
    type: 'MultiPoint';
    coordinates: Coordinates[];
}

interface LineString extends Base {
    type: 'LineString';
    coordinates: Coordinates[];
}

interface MultiLineString extends Base {
    type: 'MultiLineString';
    coordinates: Coordinates[][];
}

export interface Polygon extends Base {
    type: 'Polygon';
    coordinates: Coordinates[][];
}

interface MultiPolygon extends Base {
    type: 'MultiPolygon';
    coordinates: Coordinates[][][];
}

export interface PrimitiveGeometryCollection extends Base {
    type: 'GeometryCollection';
    geometries: PrimitiveGeometry[];
}

export interface MultiGeometryCollection extends Base {
    type: 'GeometryCollection';
    geometries: PrimitiveGeometry[];
}

export interface GeometryCollection extends Base {
    type: 'GeometryCollection';
    geometries: Geometry[];
}

export type PrimitiveGeometry = Point | LineString | Polygon;
export type MultiGeometry = PrimitiveGeometry | MultiPoint | MultiLineString | MultiPolygon;
export type Geometry = MultiGeometry | GeometryCollection;


export interface Feature extends Base {
    type: 'Feature';
    geometry: Geometry;
    properties?: Record<string, any> | null;
}

interface TopLevelFeature extends Feature {
    bbox?: BoundingBox;
    crs?: CRS;
}

interface FeatureCollection extends Base {
    type: 'FeatureCollection';
    features: Feature[];
}

export type GeoJSON = Geometry | TopLevelFeature | FeatureCollection;


export function forEachPoint(g: GeoJSON, f: (c: Coordinates) => void) {
    switch (g.type) {
        case 'Point':
            f(g.coordinates);
            break;

        case 'LineString':
        case 'MultiPoint':
            g.coordinates.forEach(c => f(c));
            break;

        case 'Polygon':
        case 'MultiLineString':
            g.coordinates.forEach(cl => cl.forEach(c => f(c)));
            break;

        case 'MultiPolygon':
            g.coordinates.forEach(cll => cll.forEach(cl => cl.forEach(c => f(c))));
            break;

        case 'GeometryCollection':
            g.geometries.forEach(g => forEachPoint(g, f));
            break;

        case 'Feature':
            forEachPoint(g.geometry, f);
            break;

        case 'FeatureCollection':
            g.features.forEach(v => forEachPoint(v, f));
            break;

        default:
            throw new Error(`Unsupported GeoJSON type ${(g as any).type}`);
    }
}


export function mapEachPoint(g: GeoJSON, f: (c: Coordinates) => Coordinates) {
    switch (g.type) {
        case 'Point':
            g.coordinates = f(g.coordinates);
            break;

        case 'LineString':
        case 'MultiPoint':
            g.coordinates = g.coordinates.map(c => f(c));
            break;

        case 'Polygon':
        case 'MultiLineString':
            g.coordinates = g.coordinates.map(cl => cl.map(c => f(c)));
            break;

        case 'MultiPolygon':
            g.coordinates = g.coordinates.map(cll => cll.map(cl => cl.map(c => f(c))));
            break;

        case 'GeometryCollection':
            g.geometries = g.geometries.map(g => mapEachPoint(g, f) as Geometry);
            break;

        case 'Feature':
            g.geometry = mapEachPoint(g.geometry, f) as Geometry;
            break;

        case 'FeatureCollection':
            g.features.map(v => mapEachPoint(v, f));
            break;

        default:
            throw new Error(`Unsupported GeoJSON type ${(g as any).type}`);
    }
    return g;
}


const lng = (c: Coordinates[]) => c.map(d => d[0]);
const lat = (c: Coordinates[]) => c.map(d => d[1]);


const minLng = (c: Coordinates[]) => Math.min.apply(null, lng(c));
const minLat = (c: Coordinates[]) => Math.min.apply(null, lat(c));
const maxLng = (c: Coordinates[]) => Math.max.apply(null, lng(c));
const maxLat = (c: Coordinates[]) => Math.max.apply(null, lat(c));


export function boundingBox(g: Geometry | Feature | FeatureCollection | GeoJSON) {
    const points: Coordinates[] = [];
    forEachPoint(g, c => points.push(c));
    return {
        left   : minLng(points),
        bottom : minLat(points),
        right  : maxLng(points),
        top    : maxLat(points)
    };
}


function getCoordinateReference(g: GeoJSON) {
    const crs = (g as any).crs as CRS | undefined;
    if (crs === undefined) return;

    if (crs.type === 'name')
        return `${crs.properties.name}`;
}


export function reproject(g: GeoJSON, to: string | ((c: Coordinates, from: string) => Coordinates), from?: string) {
    // If no source coordinate reference was provide and if the GeoJSON object
    // has no crs property, assume WGS84 (ESPG:4326).
    const crs = from || getCoordinateReference(g) || 'EPSG:4326';

    const rv = JSON.parse(JSON.stringify(g)) as GeoJSON;
    delete (rv as any).crs;

    if (typeof to === 'string') {
        const project = proj4(crs, to).forward;
        mapEachPoint(rv, c => project(c));
    } else {
        mapEachPoint(rv, c => to(c, crs));
    }

    return rv;
}


export function isFeature(geojson: any): geojson is Feature {
    return geojson.type === 'Feature';
}


export function isPrimitiveGeometry(g: Geometry): g is PrimitiveGeometry {
    return g.type === 'Point' || g.type === 'LineString' || g.type === 'Polygon';
}


export function isEmpty(data?: GeoJSON) {
    if (data === undefined) return true;

    switch (data.type) {
        case 'Point':
            // A GeoJSON point must always have coordinates and thus can never
            // be empty.
            return false;

        case 'LineString':
        case 'Polygon':
        case 'MultiPoint':
        case 'MultiLineString':
        case 'MultiPolygon':
            return data.coordinates.length === 0;

        case 'GeometryCollection':
            return data.geometries.length === 0;

        case 'Feature':
            return isEmpty(data.geometry);
            break;

        case 'FeatureCollection':
            return data.features.length === 0;
    }
}