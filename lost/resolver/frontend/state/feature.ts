import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import { searchOpenStreetMap, getFeatureName, guessFeatureType } from '../osm/feature';
import { createControlPoint, deleteControlPoint } from './control';
import { Coordinates } from '../utils/coordinates';
import { CoordinateTransform, coordinateTransform } from './transform';
import { Shape, shape as shapeSlice } from './shape';
import {
    isFeature as isGeoJSONFeature,
    isPrimitiveGeometry,
    forEachPoint,
    reproject
} from '../utils/geojson';
import { AppDispatch, RootState } from './store';
import ResolverAPI from '../api/resolver';
import GUID from '../utils/guid';


export const FeatureTypes = [ 'Area', 'Building', 'Floor', 'Apartment', 'Room', 'Way', 'Point' ] as const;
export type FeatureType = typeof FeatureTypes[number];


type AttrsType = Partial<Record<string,any>>;


export interface FeatureData {
    id?: string;
    type: FeatureType;
    name?: string;
    parent: string | null;
    indoor: boolean;
    verticalRange?: string | null;
    created?: string;
    attrs?: AttrsType;
    shape: string | null;
    controlPoints?: string[];
    image: string | null;
    transform: string | null;
}


export interface Feature extends FeatureData {
    id: string;
    name: string;
    created: string;
    controlPoints: string[];
    verticalRange: string | null;
    attrs: AttrsType;
}


export type FeatureState = Record<string, Feature>;


export const feature = createSlice({
    name: 'feature',
    initialState: {} as FeatureState,
    reducers: {
        create: {
            reducer: (state, { payload }: PayloadAction<Feature>) => {
                const f: Feature = {
                    ...payload,
                    id: (payload as any).id || GUID(),
                    controlPoints: (payload as any).controlPoints || []
                };
                state[f.id] = f;
            },
            prepare: (v: FeatureData) => ({
                payload: {
                    ...v,
                    id            : GUID(),
                    name          : v.name || `Unnamed ${v.type}`,
                    created       : v.created || (new Date()).toISOString(),
                    attrs         : v.attrs ? {...v.attrs} : {},
                    verticalRange : v.verticalRange || null,
                    controlPoints : v.controlPoints || []
                }
            })
        },
        delete(state, { payload: ids }: PayloadAction<string[]>) {
            ids.forEach(id => { delete state[id]; });
        },
        setName(state, { payload: { id, name } }: PayloadAction<{ id: string, name: string }>) {
            const f = state[id];
            if (!f) throw Error('Invalid feature ID');
            f.name = name;
        },
        setShape(state, { payload: { id, shape } }: PayloadAction<{ id: string, shape: string | null }>) {
            const f = state[id];
            if (!f) throw Error('Invalid feature ID');
            f.shape = shape;
        },
        setImage(state, { payload: { id, image } }: PayloadAction<{ id: string, image: string | null }>) {
            const f = state[id];
            if (!f) throw Error('Invalid feature ID');
            f.image = image;
        },
        setTransform(state, { payload: { id, transform } }: PayloadAction<{ id: string, transform: string | null }>) {
            const f = state[id];
            if (!f) throw Error('Invalid feature ID');
            f.transform = transform;
        },
        setAttrs(state, { payload: { id, attrs } }: PayloadAction<{ id: string, attrs: AttrsType }>) {
            const f = state[id];
            if (!f) throw Error('Invalid feature ID');
            f.attrs = JSON.parse(JSON.stringify(attrs));
        },
        setControlPoints(state, { payload: { id, controlPoints } }: PayloadAction<{ id: string, controlPoints: string[] }>) {
            const f = state[id];
            if (!f) throw Error('Invalid feature ID');
            f.controlPoints = controlPoints;
        },
        addControlPoint(state, { payload: { featureId, controlPointIds }}: PayloadAction<{ featureId: string, controlPointIds: string[] }>) {
            const feature = state[featureId];
            if (!feature) throw Error('Invalid feature ID');

            controlPointIds.forEach(id => {
                if (!feature.controlPoints.includes(id)) feature.controlPoints.push(id);
            });
        }
    },
    extraReducers: {
        // Monitor the action that deletes control points and remove the
        // correponding points from any features that have them. The action type
        // needs to be kept synchronized with the corresponding action in the
        // control point slice.
        'controlPoint/delete': (state, { payload: cpIds }: PayloadAction<string[]>) => {
            Object.keys(state).forEach(id => {
                const feature = state[id];
                feature.controlPoints = feature.controlPoints.filter(cpId => !cpIds.includes(cpId));
            });
        }
    }
});


export const {
    create   : createFeature,
    setName  : setFeatureName,
    setAttrs : setFeatureAttrs,
    setShape : setFeatureShape,
    setControlPoints: setFeatureControlPoints,
    addControlPoint
} = feature.actions;


export function clearRasterBase(id: string) {
    return (dispatch: AppDispatch) => {
        dispatch(feature.actions.setImage({ id, image: null }));
        dispatch(feature.actions.setTransform({ id, transform: null }));
    };
}


export function setRasterBase(id: string, image: string) {
    return (dispatch: AppDispatch) => {
        dispatch(feature.actions.setImage({ id, image }));
        const { payload: transform } = dispatch(coordinateTransform.actions.create());
        dispatch(feature.actions.setTransform({ id, transform: transform.id }));
    };
}


export function deleteFeature(f: Feature[]) {
    return (dispatch: AppDispatch) => {
        const cpIds = f.reduce((acc, b) => acc.concat(b.controlPoints), [] as string[]);
        dispatch(feature.actions.delete(f.map(f => f.id)));
        dispatch(deleteControlPoint(cpIds));
    };
}


export function initializeControlPoints(feature: Feature, state: RootState, shape?: Shape) {
    return (dispatch: AppDispatch) => {
        // Extract an initial set of reference points for the building from its
        // corner points.
        if (!shape) {
            if (!feature.shape) throw new Error('Could not extract control points from feature (no GeoJSON data)');
            shape = state.shape[feature.shape];
        }

        const controlPoints = feature.controlPoints.map(id => state.controlPoint[id]);

        const create: Coordinates[] = [];
        forEachPoint(shape, ([ x, y ]) => {
            if (!controlPoints.filter(({ coordinates: [ a, b ] }) => a === x && b === y).length)
                create.push([ x, y ]);
        });
        const { payload: cps } = dispatch(createControlPoint(create));
        dispatch(addControlPoint({ featureId: feature.id, controlPointIds: cps.map(c => c.id) }));
    };
}


export function importFromOSM(query: string, state: RootState, osmData?: any) {
    return async (dispatch: AppDispatch) => {
        if (osmData === undefined)
            osmData = await searchOpenStreetMap(query);

        if (!isGeoJSONFeature(osmData))
            throw new Error('Got unsupported GeoJSON type from OpenStreetMap');

        if (!isPrimitiveGeometry(osmData.geometry))
            throw new Error('Only primitive GeoJSON geometries are supported');

        const attrs = {...osmData.properties};
        if (query) attrs.query = query;

        const {
            payload: shape
        } = dispatch(shapeSlice.actions.create([ osmData.geometry ]));

        if (attrs.id)
            attrs.mapUrl = `https://openstreetmap.org/${attrs.id}`;

        const { payload } = dispatch(feature.actions.create({
            type        : guessFeatureType(osmData),
            name        : getFeatureName(osmData) || query,
            parent      : null,
            image       : null,
            indoor      : true,
            shape       : shape.id,
            transform   : 'WGS84',
            attrs
        }));

        dispatch(initializeControlPoints(payload, state, shape));
    };
}


function findTransform(feature: Feature | null, features: FeatureState): string | null {
    if (!feature) return null;
    if (feature.transform) return feature.transform;
    if (feature.parent) return findTransform(features[feature.parent] || null, features);
    return null;
}



export function findShape(feature: Feature | null, features: FeatureState): [ string | null, string | null ] {
    if (!feature) return [ null, null ];
    if (feature.shape) return [ feature.shape, findTransform(feature, features) ];
    if (feature.parent) return findShape(features[feature.parent], features);
    return [ null, null ];
}


export class FeatureAPI {
    public readonly data: Feature;
    private readonly state: RootState;

    constructor(feature: string | Feature, state: RootState) {
        if (typeof feature === 'string') this.data = state.feature[feature];
        else this.data = feature;

        this.state = state;
    }

    private get shapeId(): [string, string] {
        if (this.data.shape) return [this.data.shape, this.data.id];

        const features = this.state.feature;

        for(let p = this.data.parent; p !== null; p = features[p].parent) {
            const f = features[p];
            if (f.shape) return [f.shape, f.id];
        }
        throw new Error('Shape not found in feature tree');
    }

    public get shape(): Shape {
        const shapes = this.state.shape;
        return shapes[this.shapeId[0]];
    }

    public crsId(featureId?: string): string {
        const features = this.state.feature;
        const f = featureId? features[featureId] : this.data;

        if (f.transform) return f.transform;

        for(let p = f.parent; p !== null; p = features[p].parent) {
            const v = features[p];
            if (v.transform) return v.transform;
        }
        throw new Error('Coordinate reference not found in feature tree');
    }

    public rasterBase(featureId?: string): [ string | null, string | null ] {
        const features = this.state.feature;
        const f = featureId? features[featureId] : this.data;

        if (f.image) return [ f.image, f.transform ];

        for(let p = f.parent; p !== null; p = features[p].parent) {
            const v = features[p];
            if (v.image) return [ v.image, v.transform ];
        }
        return [ null, null ];
    }

    private crs(featureId?: string): CoordinateTransform | null {
        const id = this.crsId(featureId);
        if (id === 'WGS84') return null;
        const transforms = this.state.coordinateTransform;
        return transforms[id];
    }

    async wgs84Shape(): Promise<Shape> {
        const shapes = this.state.shape;
        const [ shapeId, featureId ] = this.shapeId;

        const shape = shapes[shapeId];
        const t = this.crs(featureId);
        if (t === null) return shape;

        const tAPI = new CoordinateTransformAPI(t, this.state);
        await tAPI.estimate();
        const rv = reproject(shape, point => tAPI.toWGS84(point));
        rv.id = shape.id;
        return rv as Shape;
    }
}


export function upload(state: FeatureState) {
    const api = new ResolverAPI();
    return api.invoke('feature', Object.values(state), 'PUT');
}