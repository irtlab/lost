import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import { AppDispatch } from './store';

const defaultTimeout = 10000;

type AlertVariant = 'primary' | 'secondary' | 'success' | 'danger' | 'warning' | 'info' | 'light' | 'dark';

interface Alert {
    id: number;
    message: string;
    variant: AlertVariant;
}

export type AlertState = Alert[];


let alertId = 0;


export const alert = createSlice({
    name: 'alert',
    initialState: [] as AlertState,
    reducers: {
        create: {
            reducer: (state: AlertState, action: PayloadAction<Alert>) => {
                const { id, message, variant } = action.payload;
                state.unshift({ id, message, variant });
            },
            prepare: (message: string, variant: AlertVariant = 'danger') => ({
                payload: { id: alertId++, message, variant }
            })
        },
        delete: (state: AlertState, action: PayloadAction<number>) => (
            state.filter(v => v.id !== action.payload)
        )
    }
});


export function showAlert(message: string, variant?: AlertVariant, timeout = defaultTimeout) {
    return (dispatch: AppDispatch) => {
        const rv = dispatch(alert.actions.create(message, variant));
        setTimeout(() => {
            dispatch(alert.actions.delete(rv.payload.id));
        }, timeout);
        return rv;
    };
}


export function alertOnError<T = unknown>(f: (dispatch?) => Promise<T>, variant?: AlertVariant, timeout = defaultTimeout) {
    return (dispatch: AppDispatch) => {
        return f(dispatch).catch(error => {
            dispatch(showAlert(error.message, variant, timeout));
        });
    };
}