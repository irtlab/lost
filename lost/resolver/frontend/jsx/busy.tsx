import React from 'react';
import { useSelector } from 'react-redux';
import { Modal, Spinner } from 'react-bootstrap';
import { BusyState } from '../state/busy';
import { RootState } from '../state/store';


export function BusyModal({ show, message }: { show: boolean, message: string }) {
    return (
        <Modal show={show} animation={false} centered size='sm'>
            <Modal.Body>
                <div className="text-center" style={{ marginTop: '1rem', marginBottom: '1rem' }}>
                    <Spinner className="text-center" animation="grow" variant="primary"/>
                </div>
                <div className="text-center">
                    {message}
                </div>
            </Modal.Body>
        </Modal>
    );
}


export function BusyCurtain() {
    const busy = useSelector<RootState, BusyState>(s => s.busy);
    return (
        <BusyModal
            show={Object.keys(busy).length != 0}
            message={Object.values(busy)[0]}
        />
    );
}
