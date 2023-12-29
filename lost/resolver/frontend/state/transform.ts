import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import ResolverAPI from '../api/resolver';
import GUID from '../utils/guid';
import { ControlLink } from './control';


export type TransformMatrix = number[][];


export interface CoordinateTransformData {
    id?: string;
    controlLinks: Record<string,ControlLink>;
}


export interface CoordinateTransform extends CoordinateTransformData {
    id: string;
}


export type CoordinateTransformState = Record<string,CoordinateTransform>;


export const coordinateTransform = createSlice({
    name: 'coordinateTransform',
    initialState: {} as CoordinateTransformState,
    reducers: {
        create: {
            reducer(state, { payload }: PayloadAction<CoordinateTransform>) {
                state[payload.id] = payload;
            },
            prepare: () => ({
                payload: {
                    id: GUID(),
                    controlLinks: {},
                    toWGS84: null,
                    fromWGS84: null
                }
            })
        },
        createControlLink: {
            reducer(state, { payload: { id, link } }: PayloadAction<{ id: string, link: ControlLink }>) {
                const t = state[id];
                t.controlLinks[link.id] = link;
            },
            prepare: (id: string, { wgs84Point, imagePoint}: { wgs84Point: string, imagePoint: string }) => ({
                payload: { id, link: { id: GUID(), wgs84Point, imagePoint }}
            })
        },
        deleteControlLink(state, { payload: { id, link }}: PayloadAction<{ id: string, link: string[] }>) {
            const t = state[id];
            if (!t) throw new Error('Invalid coordinate transform ID');
            link.forEach(id => { delete t.controlLinks[id]; });
        }
    }
});


export function hasLink(t: CoordinateTransform, wgs84Point: string, imagePoint: string) {
    return Object.values(t.controlLinks).filter(link => {
        if (link.wgs84Point === wgs84Point && link.imagePoint === imagePoint)
            return true;
        return false;
    }).length !== 0;
}


export function upload(state: CoordinateTransformState) {
    const api = new ResolverAPI();
    return api.invoke('coordinate_transform', Object.values(state), 'PUT');
}