import React, { useState, useEffect, useMemo, useContext, useRef } from 'react';
import { useSelector } from 'react-redux';
import { Container, Row, Col, Button, Form, Table } from 'react-bootstrap';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { ContainerDimensions } from './utils';
import { Routes, Route, useResolvedPath, useNavigate, Navigate, useParams } from 'react-router-dom';
import { RasterImage, ImageState, deleteImage } from '../state/image';
import { faTrash, faUpload } from '@fortawesome/free-solid-svg-icons';
import { FitCartesianCoordinates, CoordinateTransform } from '../utils/coordinates';
import { alertOnError } from '../state/alert';
import busy, { busyWhile } from '../state/busy';
import { uploadImages, setImageName } from '../state/image';
import Image from './overlay/image';
import { loadHTMLImage } from '../utils/image';
import { Stack, Overlay, ErrorMessage } from './utils';
import { RootState } from '../state/store';
import { useAppDispatch } from '../utils/hooks';
import { useGetImagesQuery } from '../state/image';


function UploadButton() {
    const ref = useRef<any>(null),
        dispatch = useAppDispatch();

    return (<>
        <Form.Control ref={ref} type="file" multiple accept="image/*" style={{display: "none"}} onChange={() => {
            const { files } = ref.current;
            if (files.length)
                dispatch(alertOnError(busyWhile(uploadImages(files), 'Uploading image(s). Please wait.')));
            return false;
        }} onClick={() => {
            ref.current.value = null;
        }}/>
        <div className="d-grid gap-2">
            <Button variant="outline-secondary" onClick={e => { e.preventDefault(); ref.current.click(); }}>
                <FontAwesomeIcon icon={faUpload}/>&nbsp;Upload image(s)
            </Button>
        </div>
    </>);
}


const formatDate = (cell) => (
    cell !== undefined ? new Date(cell).toLocaleString() : ''
);


const formatDimensions = (cell, row) => (
    cell !== undefined ? `${row.width}x${row.height}` : ''
);

let id: string | undefined = undefined;

function ImageList() {
    const dispatch = useAppDispatch();
    const { data: images = {} } = useGetImagesQuery();

    const navigate = useNavigate();
    const path = '/image';
    // const { path } = useRouteMatch();
    const [ selected, setSelected ] = useState<Set<string>>(new Set([]));

    // When the data set is updated, check the current selection and remove any
    // items that are no longer in the data set.
    useEffect(() => {
        selected.forEach(id => { images[id] || selected.delete(id); });
        setSelected(new Set(selected));
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [ images ]);

    const tableData = useMemo(() => Object.values(images), [ images ]);

    function open(id: string) {
        navigate(`${path}/${id}/edit`);
    }

    function onSelect(row: RasterImage, isSelected) {
        if (isSelected) {
            setSelected(new Set(selected.add(row.id)));
        } else {
            selected.delete(row.id);
            setSelected(new Set(selected));
        }
    }

    function onSelectAll(isSelected, rows: RasterImage[]) {
        if (isSelected) {
            setSelected(new Set(rows.map(r => r.id)));
        } else {
            setSelected(new Set());
        }
    }

    function deleteSelected() {
        const img = [...selected].reduce((acc, id) => {
            const i = images[id];
            if (i) acc.push(i);
            return acc;
        }, [] as RasterImage[]);

        dispatch(alertOnError(busyWhile(deleteImage(img), 'Deleting image(s). Please wait.')));
    }

    const columns = [{
        dataField: 'id',
        text: 'ID',
        headerAlign: 'left',
        hidden: false
    }, {
        dataField: 'name',
        text: 'Name',
        headerAlign: 'center',
        sort: true
    }, {
        dataField: 'fileName',
        text: 'Filename',
        headerAlign: 'center',
        sort: true
    }, {
        dataField: 'width',
        text: 'Dimensions [px]',
        headerAlign: 'center',
        align: 'center',
        formatter: formatDimensions
    }, {
        dataField: 'size',
        text: 'Size [B]',
        sort: true,
        headerAlign: 'right',
        align: 'right'
    }, {
        dataField: 'created',
        text: 'Created',
        sort: true,
        headerAlign: 'center',
        align: 'center',
        formatter: formatDate
    }, {
        dataField: 'updated',
        text: 'Updated',
        sort: true,
        headerAlign: 'center',
        align: 'center',
        formatter: formatDate
    }];

    return (
        <Container fluid style={{ marginTop: '1em' }}>
            <Row style={{ marginBottom: '1em' }}>
                <Col xs='auto'>
                    <UploadButton/>
                </Col>
            </Row>
            <Row style={{ marginBottom: '1em' }}>
                <Col xs='auto'>
                    <Button disabled={!selected.size} variant='outline-dark' onClick={deleteSelected}>
                        <FontAwesomeIcon icon={faTrash}/>&nbsp;Delete
                    </Button>
                </Col>
            </Row>
            <Row>
                <Col>
                    <Table striped bordered hover>
                        <thead>
                            <tr>
                                <th style={{ textAlign: 'center' }}><Form.Check type='checkbox' id='check-all'/></th>
                                {columns.map(({ text, hidden, headerAlign }, i) => hidden ? null : <th style={{ textAlign: headerAlign }} key={i}>{text}</th>)}
                            </tr>
                        </thead>
                        <tbody>
                            {Object.values(images).map((img, i) => {
                                return (
                                    <tr key={i}>
                                        <td style={{ textAlign: columns[0].align }}>{img.id}</td>
                                        <td style={{ textAlign: columns[1].align }}>{img.name}</td>
                                        <td style={{ textAlign: columns[2].align }}>{img.fileName}</td>
                                        <td style={{ textAlign: columns[3].align }}>{`${img.width}x${img.height}`}</td>
                                        <td style={{ textAlign: columns[4].align }}>{img.size}</td>
                                        <td style={{ textAlign: columns[5].align }}>{formatDate(img.created)}</td>
                                        <td style={{ textAlign: columns[6].align }}>{formatDate(img.updated)}</td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </Table>
                </Col>
            </Row>
        </Container>
    );
}


function ImageNameEditor({ image }: { image: RasterImage }) {
    const [ name, setName ] = useState<string>(image.name ? image.name : '');
    const dispatch = useAppDispatch();

    useEffect(() => {
        setName(image.name ? image.name : '');
    }, [ image ]);

    return (
        <Form.Control
            onChange={e => { setName(e.target.value); }}
            onBlur={() => image.id && dispatch(setImageName({ id: image.id, name }))}
            spellCheck={false}
            value={name}
        />
    );
}


function Editor({ image }: { image: RasterImage }) {
    const dispatch = useAppDispatch();

    useEffect(() => {
        dispatch(alertOnError(busyWhile(async () => {
            await loadHTMLImage(image.src);
        })));
    }, [ image, dispatch ]);

    const createTransform = (viewWidth, viewHeight) => (
        new FitCartesianCoordinates(
            { width: viewWidth, height: viewHeight },
            { width: image.width, height: image.height })
    );

    return (
        <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100%', userSelect: 'none' }}>
            <Container fluid style={{ marginTop: "1rem", marginBottom: "1rem" }}>
                <Row>
                    <Col>
                        <ImageNameEditor image={image}/>
                    </Col>
                </Row>
            </Container>
            <Stack style={{ flexGrow: 1 }}>
                <ContainerDimensions>{({ width, height }) => (
                    <CoordinateTransform.Provider value={createTransform(width, height)}>
                        <Overlay>
                            <Image url={image.src!} viewWidth={width} viewHeight={height}/>
                        </Overlay>
                    </CoordinateTransform.Provider>
                )}</ContainerDimensions>
            </Stack>
        </div>
    );
}


function LookupImage({ component: C }: { component: any }) {
    const { pathname } = useResolvedPath('');
    const { id } = useParams<{ id: string | undefined }>();
    const { data: images = {} } = useGetImagesQuery();
    const image = id ? images[id] : undefined;

    if (id && !image)
        return <ErrorMessage>Image not found.</ErrorMessage>;

    if (!id) return <Navigate to={pathname} replace />
    
    return <C image={image}/>;
}


export default function Main() {
    const dispatch = useAppDispatch();
    const { isFetching, isSuccess, isError, error } = useGetImagesQuery();

    if (isFetching && id === undefined) {
        id = dispatch(busy.actions.start('Loading image(s). Please wait.')).payload.id;
    }

    if (!isFetching && id !== undefined) {
        dispatch(busy.actions.stop(id));
        id = undefined;
    }

    if (isFetching) return;

    return (
        <Routes>
            <Route path='/' element={<ImageList/>} />
            <Route path='/:id/edit' element={<LookupImage component={Editor}/>}/>
        </Routes>
    );
}
