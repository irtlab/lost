import React from 'react';
import { Alert } from 'react-bootstrap';
import { useSelector } from 'react-redux';
import { alert, AlertState } from '../state/alert';
import { RootState } from '../state/store';
import { useAppDispatch } from '../utils/hooks';


export default function Alerts() {
    const data = useSelector<RootState, AlertState>(state => state.alert);
    const dispatch = useAppDispatch();
    return (
        <div className='alert-wrapper'>
            {data.map(a => (
                <Alert
                    className='alert'
                    key={a.id}
                    onClose={() => dispatch(alert.actions.delete(a.id))}
                    variant={a.variant}
                    dismissible
                >
                    {a.message}
                </Alert>
            ))}
        </div>
    );
}
