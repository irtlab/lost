import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import { Coordinates } from '../utils/coordinates';
import ResolverAPI from '../api/resolver';
import GUID from '../utils/guid';


export interface ControlLink {
    id: string;
    wgs84Point: string;
    imagePoint: string;
}


export interface ControlPoint {
    id: string;
    crsFeature?: string;
    coordinates: Coordinates;
}


export type ControlPointState = Record<string, ControlPoint>;


export const controlPoint = createSlice({
    name: 'controlPoint',
    initialState: {} as ControlPointState,
    reducers: {
        create: {
            reducer: (state, { payload }: PayloadAction<ControlPoint[]>) => {
                payload.forEach(cp => { state[cp.id] = cp; });
            },
            prepare: (coordinates: Coordinates[], crsFeature?: string) => ({
                payload: coordinates.map(coord => {
                    const rv: any = { id: GUID(), coordinates: coord };
                    if (crsFeature) rv.crsFeature = crsFeature;
                    return rv;
                })
            })
        },
        update(state, { payload }: PayloadAction<ControlPoint[]>) {
            payload.forEach(ref => {
                const old = state[ref.id];
                if (old === undefined) throw Error('Invalid control point ID');
                state[ref.id] = {...old, ...ref};
            });
        },
        move: {
            reducer(state, { payload }: PayloadAction<{ id: string, coordinates: Coordinates }>) {
                const { id, coordinates } = payload;
                const cp = state[id];
                if (!cp) throw new Error('Invalid control point ID');
                cp.coordinates = [...coordinates];
            },
            prepare(id: string, coordinates: Coordinates) {
                return { payload: { id, coordinates } };
            }
        },
        delete(state, { payload }: PayloadAction<string[]>) {
            payload.forEach(id => { delete state[id]; });
        },
    }
});


export const {
    create : createControlPoint,
    update : updateControlPoint,
    delete : deleteControlPoint,
    move   : moveControlPoint
} = controlPoint.actions;


export function upload(state: ControlPointState) {
    const api = new ResolverAPI();
    return api.invoke('control_point', Object.values(state).map(point => ({
        type: 'Point',
        ...point,
        crs: {
            type: 'name',
            properties: {
                name: point.crsFeature ? `feature:${point.crsFeature}` : 'EPSG:4326'
            }
        }
    })), 'PUT');
}
