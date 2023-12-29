import React from 'react';
import proj4 from 'proj4';


export type CoordinatesType = 'Screen' | 'Cartesian' | 'Geo';


interface Attrs {
    attrs?: Record<string, any | undefined>;
}


/**
 * Two or three dimensional coordinates in the Cartesian coordinate system. By
 * convertion, the x coordinate is measured along a horizontal axis, oriented
 * from left to right. The y coordinate is measured along a vertical axis,
 * oriented from bottom to top. The optional z coordinate represents height
 * above the xy plane, oriented towards the viewer.
 */
export interface CartesianCoordinates extends Attrs {
    x: number;
    y: number;
    z?: number;
}


/**
 * Two or three dimentional coordinates in the Cartesian coordinate system. In
 * this case, the coordinates are oriented according to the convention adopted
 * for computer screens, i.e., the left coordinate is oriented from left to
 * right, the top coordinate is oriented from top to bottom, and the optional z
 * coordinate represents height and is oriented towards the viewer.
 */
export interface ScreenCoordinates extends Attrs {
    left: number;
    top: number;
    z?: number;
}


/**
 * Two or three dimensional coordinates in the World Geodetic System (WGS) 84.
 * The coordinates represent longitude, latituce, and (optionally) altitude. The
 * longitude coordinate specifies an east-west position on the Earth's surface.
 * It is zero at the IERS Reference Meridian near the Greenwich meridian and
 * ranges from -90 to 90. The latitude coordinate specifieds a south-north
 * position on the Earth's surface. It is zero at the Equator and ranges from
 * -90 at the South Pole to 90 at the North Pole. The optional altitude
 * coordinate specifies the height above the WGS 84 reference ellipsoid (same as
 * GPS).
 */
export interface GeoCoordinates extends Attrs {
    lng: number;
    lat: number;
    alt?: number;
}


/**
 * The dimensions of a two or three dimensional area.
 */
export interface Dimensions {
    width: number;
    height: number;
    depth?: number;
}


export type Coordinates = [number, number];

export function isCartesian(c: GeoCoordinates | ScreenCoordinates | CartesianCoordinates):
 c is CartesianCoordinates {
    return typeof (c as any).x === 'number'
        && typeof (c as any).y === 'number'
        && (typeof (c as any).z === 'number' || (c as any).z === undefined);
}


export function isScreen(c: GeoCoordinates | ScreenCoordinates | CartesianCoordinates): c is ScreenCoordinates {
    return typeof (c as any).left === 'number'
        && typeof (c as any).top === 'number'
        && (typeof (c as any).z === 'number' || (c as any).z === undefined);
}


export function isGeo(c: GeoCoordinates | ScreenCoordinates | CartesianCoordinates): c is GeoCoordinates {
    return typeof (c as any).lng === 'number'
        && typeof (c as any).lat === 'number'
        && (typeof (c as any).alt === 'number' || (c as any).alt === undefined);
}


/**
 * A bounding box defined by dimensions and an optional origin. If the origin is
 * not set, it is set to the origin of the Cartesian coordinate system.
 */
class Bounds {
    readonly origin: CartesianCoordinates;
    readonly dimensions: Dimensions;

    get width()  { return this.dimensions.width; }
    get height() { return this.dimensions.height; }
    get depth()  { return this.dimensions.depth; }

    constructor(dimensions: Dimensions, origin: CartesianCoordinates = { x: 0, y: 0 }) {
        this.dimensions = {...dimensions};
        this.origin = {...origin};
    }
}


/**
 * A coordinate transformation from Cartesian coordinates to screen coordinates
 * such that the given bounding box in Cartesian coordinates defined by 'origin'
 * and 'extent' is scaled and centered into the given screen bounding box
 * repreesented by its dimensions 'view'.
 *
 * Limitation: Currently only works in 2D.
 */
export abstract class FitTransform {
    readonly bounds: Bounds;
    readonly view: Bounds;
    readonly type: CoordinatesType;

    get offsetTop() {
        return (this.view.height - this.bounds.height * this.scale) / 2;
    }

    get offsetLeft() {
        return (this.view.width - this.bounds.width * this.scale) / 2;
    }

    get offset(): ScreenCoordinates {
        return {
            top: this.offsetTop,
            left: this.offsetLeft
        };
    }

    get scale() {
        const sw = this.view.width / this.bounds.width;
        const sh = this.view.height / this.bounds.height;
        return Math.min(sw, sh);
    }

    abstract toView(loc: Coordinates): ScreenCoordinates;
    abstract fromView(loc: ScreenCoordinates): Coordinates;

    constructor(type: CoordinatesType, view: Dimensions, extent: Dimensions, origin?: CartesianCoordinates, viewOrigin?: CartesianCoordinates) {
        this.type = type;
        this.view = new Bounds(view, viewOrigin);
        this.bounds = new Bounds(extent, origin);

        this.toView = this.toView.bind(this);
        this.fromView = this.fromView.bind(this);
    }
}


export class FitScreenCoordinates extends FitTransform {
    constructor(view: Dimensions, extent: Dimensions, origin?: CartesianCoordinates, viewOrigin?: CartesianCoordinates) {
        super('Screen', view, extent, origin, viewOrigin);
    }

    toView([ left, top ]: Coordinates): ScreenCoordinates {
        const { view, bounds } = this;
        const { origin } = bounds;
        const rv: ScreenCoordinates = {
            left : Math.round((left - origin.x) * this.scale + this.offsetLeft) + view.origin.x,
            top  : Math.round((top - origin.y) * this.scale + this.offsetTop) + view.origin.y
        };
        return rv;
    }

    fromView({ left, top }: ScreenCoordinates): Coordinates {
        const { view, bounds } = this;
        const { origin } = bounds;
        const rv: ScreenCoordinates = {
            left : origin.x + Math.round(((left - view.origin.x) - this.offsetLeft) / this.scale),
            top  : origin.y + Math.round(((top - view.origin.y) - this.offsetTop) / this.scale)
        };
        return [ rv.left, rv.top ];
    }
}


export class FitCartesianCoordinates extends FitTransform {
    constructor(view: Dimensions, extent: Dimensions, origin?: CartesianCoordinates, viewOrigin?: CartesianCoordinates) {
        super('Cartesian', view, extent, origin, viewOrigin);
    }

    toView([ x, y ]: Coordinates): ScreenCoordinates {
        const { view, bounds } = this;
        const { origin } = bounds;
        const rv: ScreenCoordinates = {
            left : Math.round((x - origin.x) * this.scale + this.offsetLeft) + view.origin.x,
            top  : Math.round((bounds.height - (y - origin.y) - 1) * this.scale + this.offsetTop) + view.origin.y
        };
        return rv;
    }

    fromView({ left, top }: ScreenCoordinates): Coordinates {
        const { view, bounds } = this;
        const { origin } = bounds;
        const rv: CartesianCoordinates = {
            x : origin.x + Math.round(((left - view.origin.x) - this.offsetLeft) / this.scale),
            y : origin.y + bounds.height - 1 - Math.round(((top - view.origin.y) - this.offsetTop) / this.scale)
        };
        return [ rv.x, rv.y ];
    }
}


export class FitGeoCoordinates extends FitTransform {
    webMercator: proj4.Converter;

    constructor(view: Dimensions, extent: Dimensions, origin?: CartesianCoordinates, viewOrigin?: CartesianCoordinates) {
        super('Geo', view, extent, origin, viewOrigin);
        this.webMercator = proj4('EPSG:4326', 'EPSG:3857');
    }

    toView([ lng, lat ]: Coordinates): ScreenCoordinates {
        const [ x, y ] = this.webMercator.forward([ lng, lat ]);
        const { bounds, view } = this;
        const { origin } = bounds;
        const rv: ScreenCoordinates = {
            left : Math.round((x - origin.x) * this.scale + this.offsetLeft) + view.origin.x,
            top  : Math.round((origin.y - y) * this.scale + this.offsetTop) + view.origin.y
        };
        return rv;
    }

    fromView({ left, top }: ScreenCoordinates): Coordinates {
        const { bounds, view } = this;
        const { origin } = bounds;
        const x = origin.x + ((left - view.origin.x) - this.offsetLeft) / this.scale;
        const y = origin.y - ((top - view.origin.y) - this.offsetTop) / this.scale;
        return this.webMercator.inverse([ x, y ]);
    }
}


export const CoordinateTransform = React.createContext<FitTransform>({} as FitTransform);


const earthRadius = 6371008.7714;
const degToRad = (deg: number) => Math.PI / 180 * deg;


// Haversine formula for calculating distance in meters between a pair of WGS84
// coordinates
export function calculateDistance(a: GeoCoordinates, b: GeoCoordinates) {
    const dLat = degToRad(b.lat - a.lat),
        dLon = degToRad(b.lng - a.lng),
        A = Math.sin(dLat / 2) * Math.sin(dLat / 2)
            + Math.cos(degToRad(a.lat)) * Math.cos(degToRad(b.lat))
            * Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return earthRadius * 2 * Math.atan2(Math.sqrt(A), Math.sqrt(1 - A));
}
