import React, { useState, useMemo, useEffect, useContext, useRef } from 'react';
import { useRouteMatch, Route, Redirect, Switch, useHistory, useParams, generatePath, useLocation } from 'react-router-dom';
import { useSelector, useDispatch } from 'react-redux';
import L from 'leaflet';
import { MapContainer, GeoJSON as GeoJSONLayer, ZoomControl, ImageOverlay, ScaleControl, LayersControl, FeatureGroup, Circle, CircleProps } from 'react-leaflet';
import { Row, Col, InputGroup, Form, Button, Modal} from 'react-bootstrap';
import { busyWhile } from '../state/busy';
import { alertOnError } from '../state/alert';
import { UserContext } from '../account';
import { GeoCoordinates } from './coordinates';
import { GeoJSON, boundingBox, isEmpty, isFeature } from './geojson';
import { searchOpenStreetMap, getFeatureName } from './osm/feature';
import { geocode } from './osm/geocode';
import { Shape } from './state/shape';
import { CoordinateTransformAPI } from './state/transform';
import { GeoState } from './state/store';
import { AppState } from '../state/store';
import { Device } from './state/device';
import { RasterImage } from './state/image';
import { FeatureAPI, importFromOSM } from './state/feature';
import { Breadcrumbs } from './breadcrumbs';
import { defaultMapCenter, defaultMapZoom, maxNativeZoom } from '../../config';


function RasterOverlay({ imageId, transformId }: { imageId: string, transformId: string }) {
    const [ preview, setPreview ] = useState<string | null>(null);
    const [ bounds, setBounds ] = useState<any>(null);
    const dispatch = useDispatch();
    const user = useContext(UserContext);
    const { url } = useSelector<AppState, RasterImage>(({ geo }) => geo.image[imageId]);
    const state = useSelector<AppState, GeoState>(({ geo }) => geo);

    useEffect(() => {
        dispatch(alertOnError(busyWhile(async function() {
            setPreview(null);
            setBounds(null);

            const tAPI = new CoordinateTransformAPI(transformId, state, user);
            const data = await tAPI.reproject(url);

            setPreview(data.url);
            setBounds(data.bounds);
        }, 'Processing image. Please wait.')));
    }, [ state, transformId, url, user, dispatch ]);

    return (preview && bounds) ? (
        <ImageOverlay key={imageId} url={preview} bounds={bounds}/>
    ) : null;
}


function FeatureView() {
    const { path } = useRouteMatch();
    const map = useRef<any>(null);
    const { id } = useParams<{ id: string | undefined }>();
    const { search } = useLocation();
    const user = useContext(UserContext);
    const history = useHistory();
    const dispatch = useDispatch();
    const [ shape, setShape ] = useState<Shape | null>(null);
    const geoState = useSelector<AppState, GeoState>(({ geo }) => geo);

    const query = useMemo(() => new URLSearchParams(search), [ search ]);
    const savedZoom = parseZoom(query.get('zoom'));
    const savedCenter = useMemo(() => parseCenter(query.get('center')), [ query ]);

    const [ rasterBase, setRasterBase ] = useState<[ string | null, string | null ]>([ null, null ]);

    function saveMapState() {
        history.replace({ pathname: generatePath(path, { id }), search: query.toString() });
    }

    function saveCenter(c: GeoCoordinates) {
        // FIXME: temporarily disabled
        return;
        query.set('center', `${c.lng.toFixed(7)}_${c.lat.toFixed(7)}`);
        saveMapState();
    }

    function saveZoom(z: number) {
        // FIXME: Temporarily disabled
        return ;
        if (z === defaultMapZoom) query.delete('zoom');
        else query.set('zoom', `${z}`);
        saveMapState();
    }

    const feature = useMemo(() => {
        return id ? new FeatureAPI(id, geoState, user) : null;
    }, [ id, geoState, user ]);

    useEffect(() => {
        dispatch(alertOnError(busyWhile(async function() {
            setShape(feature ? (await feature.wgs84Shape()) : null);
        })));
    }, [ feature, dispatch ]);

    useEffect(() => {
        setRasterBase(feature ? [...feature.rasterBase()] : [ null, null ]);
    }, [ feature ]);

    useEffect(() => {
        if (savedCenter || !shape || isEmpty(shape)) return;
        const b = boundingBox(shape);
        const ll = map.current.leafletElement;

        const ne = L.latLng(b.top, b.left);
        const sw = L.latLng(b.bottom, b.right);
        const bounds = L.latLngBounds(sw, ne);
        ll.fitBounds(bounds, { maxZoom: maxNativeZoom });
    }, [ shape, savedCenter, savedZoom ]);

    // Note: We need to unmount and remount the Map component on feature change.
    // We do that by setting the key property to the current feature's id.
    //
    // Note: disable map movements via the keyboard with keyboard={false}.
    // That's because we use onDragEnd, not endMoveEnd to detect user initiated
    // movements. onMoveEnd, unfortunately, triggers even when props are changed
    // programmatically.
    const center = savedCenter || defaultMapCenter;
    const zoom = savedZoom || defaultMapZoom;
    const [ imageId, imageTransformId ] = rasterBase;

    return (<>
        <MapContainer
            style={{ width: '100%', flex: 2 }}
            scrollWheelZoom={false}
            onDragEnd={e => { saveCenter(e.target.getCenter()); }}
            onZoomEnd={e => { saveZoom(e.target.getZoom()); }}
            center={center}
            ref={map}
            zoom={zoom}
            keyboard={false}
            zoomControl={false}
            zoomAnimation={false}
            doubleClickZoom={false}
            fadeAnimation={false}
        >
            <MapLayers>
                { imageId && imageTransformId && (
                    <LayersControl.Overlay key={imageId} name='Image' checked>
                        <RasterOverlay imageId={imageId} transformId={imageTransformId}/>
                    </LayersControl.Overlay>
                )}
                { shape && (
                    <LayersControl.Overlay key={shape.id} name='Feature' checked>
                        <GeoJSONLayer data={shape} pointToLayer={pointToLayer}/>
                    </LayersControl.Overlay>
                )}
            </MapLayers>
            <ScaleControl position='bottomleft'/>
            <ZoomControl position='topright'/>
        </MapContainer>
        <MapBar>
            <Row>
                <Col xs='auto'>
                    <Breadcrumbs
                        selected={feature ? feature.data.id : null}
                        style={borderStyle}
                    />
                </Col>
            </Row>
        </MapBar>
    </>);
}


function ImportView() {
    const map = useRef<any>(null);
    const dispatch = useDispatch();
    const [ selected, setSelected ] = useState<GeoJSON | null>(null);
    const [ query, setQuery ] = useState<string>('');
    const [ key, setKey ] = useState<number>(0);
    const state = useSelector<AppState,AppState>(state => state);
    const history = useHistory();

    function resetView() {
        setQuery('');
        setKey(key + 1);
        deselectAll();
    }

    function deselectAll() {
        setSelected(null);
    }

    function keypress(event) {
        if (event.charCode !== 13) return;
        const query = event.target.value.trim();
        if (!query) {
            resetView();
            return;
        }

        dispatch(alertOnError(busyWhile(async function() {
            const res = await geocode(query);
            if (res.length === 0) return;

            const bb = res[0].boundingbox;
            map.current.leafletElement.fitBounds(L.latLngBounds(
                [bb[0], bb[2]],
                [bb[1], bb[3]]
            ));

            deselectAll();
            setQuery(res[0].display_name);
        }, "Searching OpenStreetMap")));
    }

    function fetchGeoJSON({ lng, lat }: { lng: number, lat: number }) {
        dispatch(alertOnError(busyWhile(async function() {
            const query = `@${lat},${lng}`;

            const osmData = await searchOpenStreetMap(query);
            if (!isFeature(osmData))
                throw new Error('Got unsupported GeoJSON type from OpenStreetMap');

            setSelected(osmData);
            const name = getFeatureName(osmData);
            if (name) setQuery(name);
        }, "Searching OpenStreetMap", 0)));
    }

    function importSelected() {
        if (!selected) throw new Error('No building is selected');
        dispatch(importFromOSM(query, state, selected));
        deselectAll();
        history.push('/geo/feature');
    }

    return (<>
        <Map style={{ height: '100%' }}
            key={key}
            center={defaultMapCenter}
            zoom={defaultMapZoom}
            zoomControl={false}
            zoomAnimation={false}
            doubleClickZoom={false}
            ref={map}
            fadeAnimation={false}
            onDblClick={event => {
                const ll = map.current.leafletElement.mouseEventToLatLng(event.originalEvent);
                fetchGeoJSON(ll);
            }}
        >
            <MapLayers>
                { selected && (
                    <GeoJSONLayer key={selected.id} data={selected} color='red'/>
                )}
            </MapLayers>
            <ScaleControl position='bottomleft'/>
            <ZoomControl position='topright'/>
        </Map>
        <MapBar>
            <Row>
                <Col>
                    <InputGroup>
                        <Form.Control
                            autoFocus={true}
                            spellCheck={false}
                            value={query}
                            onChange={e => { setQuery(e.target.value); }}
                            onKeyPress={keypress}
                        />
                        <InputGroup.Append>
                            <Button
                                variant='secondary'
                                style={{ minWidth: '4em' }}
                                onClick={() => { resetView(); }}
                                title='Reset'
                            >
                                Reset
                            </Button>
                        </InputGroup.Append>
                    </InputGroup>
                </Col>
                <Col xs='auto' className='pl-0'>
                    <Button
                        variant='danger'
                        disabled={!selected}
                        onClick={() => { importSelected(); }}
                    >
                        Import
                    </Button>
                </Col>
            </Row>
        </MapBar>
    </>);
}
