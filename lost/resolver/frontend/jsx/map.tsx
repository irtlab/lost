import React, { useCallback, useState, useMemo, useRef } from 'react';
import L from 'leaflet';
import { MapContainer, LayersControl, TileLayer, useMap, useMapEvent, Rectangle } from 'react-leaflet';
import { useEventHandlers, useLeafletContext } from '@react-leaflet/core';
import { maxNativeZoom, maxZoom } from '../config';
import { GeoCoordinates } from '../utils/coordinates';
import { Container, Row, Col, InputGroup, Form, Button } from 'react-bootstrap';
import { GeoJSON, isFeature } from '../utils/geojson';
import { useAppSelector, useAppDispatch } from '../utils/hooks';
import { useNavigate } from 'react-router-dom';
import { searchOpenStreetMap, getFeatureName } from '../osm/feature';
import { geocode } from '../osm/geocode';
import { alertOnError } from '../state/alert';
import { busyWhile } from '../state/busy';


const BOUNDS_STYLE = { weight: 1 }


function pointToLayer(_feature, latLng) {
    return L.circleMarker(latLng, { radius: 8 });
}


function parseZoom(v: string | null) {
    if (v !== null) {
        const zoom = Number(v);
        if (!isNaN(zoom)) return zoom;
    }
    return null;
}


function parseCenter(loc: string | null) {
    if (loc === null) return null;

    const l = loc.split('_');
    if (l.length !== 2) return null;

    const lng = Number(l[0]);
    const lat = Number(l[1]);
    if (!isNaN(lng) && !isNaN(lat)) return { lng, lat };
    return null;
}


function MapLayers({ children }: { children: any }) {
    return (
        <LayersControl position='topleft'>
            <LayersControl.BaseLayer key='map' name='Map' checked>
                <TileLayer
                    attribution='&amp;copy <a href="http://osm.org/copyright">OpenStreetMap</a> contributors'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    maxNativeZoom={maxNativeZoom}
                    maxZoom={maxZoom}
                />
            </LayersControl.BaseLayer>
            <LayersControl.BaseLayer key='satellite' name='Satellite'>
                <TileLayer
                    attribution='&amp;copy <a href="https://google.com">Google</a>'
                    url="http://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
                    maxZoom={maxZoom}
                    maxNativeZoom={maxNativeZoom}
                    subdomains={['mt0', 'mt1', 'mt2', 'mt3']}
                />
            </LayersControl.BaseLayer>
            {children}
        </LayersControl>
    );
}


function MapBar({ children }: { children: any }) {
    return (
        <div style={{ position: 'absolute', top: '15px', left: '55px', right: '44px', zIndex: 500 }}>
            <Container fluid>
                {children}
            </Container>
        </div>
    );
}


function MinimapBounds({ parentMap, zoom }) {
    const minimap = useMap()
    const context = useLeafletContext();

    // Clicking a point on the minimap sets the parent's map center
    const onClick = useCallback((e) => {
        parentMap.setView(e.latlng, parentMap.getZoom())
    }, [parentMap]);

    useMapEvent('click', onClick)

    // Keep track of bounds in state to trigger renders
    const [bounds, setBounds] = useState(parentMap.getBounds())
    const onChange = useCallback(() => {
        setBounds(parentMap.getBounds())
        // Update the minimap's view to match the parent map's center and zoom
        minimap.setView(parentMap.getCenter(), zoom);
    }, [minimap, parentMap, zoom]);

    // Listen to events on the parent map
    const handlers = useMemo(() => ({ move: onChange, zoom: onChange }), [])
    useEventHandlers({ instance: parentMap, context }, handlers);

    return <Rectangle bounds={bounds} pathOptions={BOUNDS_STYLE} />
}


function MinimapControl({ position, zoom, style }: { position: string, zoom?: number, style?: React.CSSProperties }) {
    const parentMap = useMap()
    const mapZoom = zoom || 0
  
    // Memoize the minimap so it's not affected by position changes
    const minimap = useMemo(() => (
        <MapContainer
            style={style}
            center={parentMap.getCenter()}
            zoom={mapZoom}
            dragging={false}
            doubleClickZoom={false}
            scrollWheelZoom={false}
            attributionControl={false}
            zoomControl={false}>
            <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
            <MinimapBounds parentMap={parentMap} zoom={mapZoom} />
        </MapContainer>), []);
  
    return (
        <div className={position}>
            <div className="leaflet-control leaflet-bar">
                {minimap}
            </div>
        </div>);
}


export function MapView({ style, center, zoom, children }: { style?: React.CSSProperties, center: GeoCoordinates, zoom: number, children?: any }) {
    return (
        <MapContainer style={style} center={[center.lat, center.lng]} zoom={zoom} fadeAnimation={false} scrollWheelZoom={false}>
            <MapLayers>
                {children}
            </MapLayers>
            <MinimapControl zoom={6} style={{ width: 160, height: 160 }} position="leaflet-bottom leaflet-left" />
        </MapContainer>
    );
}


export function ImportView({ center, zoom, children }: { center: GeoCoordinates, zoom: number, children?: any }) {
    const map = useRef<any>(null);
    const dispatch = useAppDispatch();
    const [ selected, setSelected ] = useState<GeoJSON | null>(null);
    const [ query, setQuery ] = useState<string>('');
    const [ key, setKey ] = useState<number>(0);
    const state = useAppSelector(state => state);
    const navigate = useNavigate();

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
        navigate('/');
    }

    return (
        <div style={{ backgroundColor: 'red', position: "relative", width: '100%', height: '100%' }}>
            <MapView style={{ position: 'absolute', width: '100%', height: '100%' }} center={center} zoom={zoom}>
            </MapView>
            <MapBar>
                <Row>
                    <Col>
                        <InputGroup>
                            <Button variant='secondary' style={{ minWidth: '4em' }} onClick={() => { resetView(); }} title='Reset'>
                                Reset
                            </Button>
                            <Form.Control
                                autoFocus={true}
                                spellCheck={false}
                                value={query}
                                onChange={e => { setQuery(e.target.value); }}
                                onKeyPress={keypress}
                            />
                            <Button variant='danger' disabled={!selected} onClick={() => { importSelected(); }}>
                                Import
                            </Button>
                        </InputGroup>
                    </Col>
                </Row>
            </MapBar>
        </div>);
}
