import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import type { AppDispatch } from './store';
import GUID from '../utils/guid';

export type BusyState = Record<string, string>;

export const busy = createSlice({
    name: 'busy',
    initialState: {} as BusyState,
    reducers: {
        start: {
            reducer: (state, action: PayloadAction<{ id: string, msg: string }>) => {
                const { id, msg } = action.payload;
                state[id] = msg;
            },
            prepare: (msg = 'Working, please wait.') => ({
                payload: { id: GUID(), msg }
            })
        },
        stop: (state, action: PayloadAction<string>) => {
            delete state[action.payload];
        }
    }
});

export default busy;


export function busyWhile<T = unknown>(f: (dispatch) => Promise<T>, msg?: string, delay = 250) {
    return (dispatch: AppDispatch) => {
        let id: string | undefined;
        const timer = setTimeout(() => {
            id = dispatch(busy.actions.start(msg)).payload.id;
        }, delay);

        return f(dispatch).finally(() => {
            clearTimeout(timer);
            if (id) dispatch(busy.actions.stop(id));
        });
    };
}
