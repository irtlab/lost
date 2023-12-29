import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import GUID from '../utils/guid';
import { Coordinates } from '../utils/coordinates';
import { PrimitiveGeometry, PrimitiveGeometryCollection, mapEachPoint } from '../utils/geojson';
import ResolverAPI from '../api/resolver';
import { RootState } from './store';
import { FeatureAPI } from './feature';

// The shape is a GeoJSON primitive (no embedded collections) geometry
// collection augmented with a unique identifier. Other GeoJSON types are
// intentionally not supported at the top level to make editing easier.

export interface ShapeData extends PrimitiveGeometryCollection {
    id?: string;
}


export interface Shape extends ShapeData {
    id: string;
}


export type ShapeState = Record<string,Shape>;


export const shape = createSlice({
    name: 'shape',
    initialState: {} as ShapeState,
    reducers: {
        create: {
            reducer(state, { payload }: PayloadAction<Shape>) {
                state[payload.id] = payload;
            },
            prepare: (geometries?: PrimitiveGeometry[]) => ({
                payload: {
                    id: GUID(),
                    type: 'GeometryCollection',
                    geometries: geometries || []
                } as Shape // FIXME: Why is this necessary?
            })
        },
        update(state, { payload: { id, geometries }}: PayloadAction<{ id: string, geometries: PrimitiveGeometry[] }>) {
            const s = state[id];
            if (!s) throw new Error('Invalid shape ID');
            s.geometries = geometries;
        },
        appendPoint(state, { payload: { id, loc }}: PayloadAction<{ id: string, loc: Coordinates }>) {
            const s = state[id];
            if (!s) throw new Error('Invalid shape ID');
            const geom = s.geometries[s.geometries.length - 1];
            if (geom.type === 'LineString') {
                geom.coordinates.push(loc);
            } else if (geom.type === 'Polygon') {
                geom.coordinates[0].push(loc);
            } else {
                throw new Error('Invalid geometry type, expected LineString or Polygon');
            }
        },
        movePoint: {
            reducer(state, { payload }: PayloadAction<{ id: string, geometry: number, point: number, coords: Coordinates }>) {
                const { id, geometry, point, coords } = payload;
                const s = state[id];
                if (!s) throw new Error('Invalid shape ID');

                let i = 0;
                state[id].geometries[geometry] = mapEachPoint(s.geometries[geometry], (c: Coordinates) => {
                    i++;
                    if (i - 1 !== point) return c;
                    return coords;
                }) as PrimitiveGeometry;
            },
            prepare(id: string, geometry: number, point: number, coords: Coordinates) {
                return { payload: { id, geometry, point, coords } };
            }
        },
        delete(state, { payload: ids }: PayloadAction<string[]>) {
            ids.forEach(id => { delete state[id]; });
        }
    }
});

export const {
    create: createShape,
    update: updateShape,
    delete: deleteShape,
    movePoint,
    appendPoint
} = shape.actions;


export async function upload(state: RootState) {
    const api = new ResolverAPI();
    const shapes = Object.values(state.shape);
    const features = state.feature;

    const sh = await Promise.all(shapes.map(async (shape) => {
        const matching = Object.values(features).filter(f => f.shape === shape.id);
        if (matching.length !== 1) return shape;
        const feature = matching[0];
        const api = new FeatureAPI(feature, state);

        try {
            return (await api.wgs84Shape());
        } catch(error) {
            return shape;
        }
    }));

    return api.invoke('shape', sh, 'PUT');
}