import React from 'react';
import * as ReactDOM from 'react-dom/client';
import 'bootstrap';
import 'bootstrap/dist/css/bootstrap.css';
import "leaflet/dist/leaflet.css";
import { DndProvider } from 'react-dnd';
import { TouchBackend } from 'react-dnd-touch-backend';
import { createBrowserRouter, RouterProvider, Outlet } from "react-router-dom";
import { Provider as StoreProvider } from 'react-redux';

import NavBar from "./navbar";
import Alerts from "./alert";
import Images from "./image";
import { BusyCurtain } from './busy';
import { defaultMapCenter, defaultMapZoom } from '../config';
import { MapView, ImportView } from './map';
import '../style.css';
import { store } from '../state/store';


// The following global variables are generated for us by the build system (Webpack)
declare global {
    const NODE_ENV            : string | undefined;
    const GIT_VERSION         : string | undefined;
    const BUILD_DATE          : string | undefined;
    const npm_package_name    : string | undefined;
    const npm_package_version : string | undefined;
}


function Layout() {
    return (
        <div style={{ display: 'flex', flexDirection: 'row', minHeight: '100vh' }}>
            <NavBar/>
            <Alerts/>
            <div style={{ display: 'flex', flexGrow: 1, flexDirection: 'column' }}>
                <Outlet/>
            </div>
            <BusyCurtain/>
        </div>
    );
}

const router = createBrowserRouter([{
    path: "/",
    element: <Layout/>,
    children: [{
        path: '/',
        element: <MapView style={{ flexGrow: 1 }} center={defaultMapCenter} zoom={defaultMapZoom}/>
    }, {
        path: '/import/*',
        element: <ImportView center={defaultMapCenter} zoom={defaultMapZoom}/>
    }, {
        path: '/images/*',
        element: <Images/>
    }, {
        path: '/features/*',
        element: <p>Features</p>
    }]
}], {
    future: {
        v7_relativeSplatPath: true
    }
}); 


function Main() {
    return (
        <React.StrictMode>
            <StoreProvider store={store}>
                <DndProvider backend={TouchBackend} options={{ enableMouseEvents: true }}>
                    <RouterProvider router={router}/>
                </DndProvider>
            </StoreProvider>
        </React.StrictMode>
    );
}


/**
 * Provide a function called 'debug' on the global windows object that can be
 * used to enable or disable debugging messages in the JavaScript console.
 * @param prefix Namespace for the NPM debug module
 */
function initDebugging(prefix: string) {
    if (NODE_ENV === 'development')
        console.log(`Use function debug() to configure debugging in the JavaScript console`);

    (window as any).debug = (onoff: boolean) => {
        if (typeof onoff !== 'boolean') {
            console.log('Usage: debug(true|false)');
            return;
        }

        if (onoff) localStorage.debug = `${prefix}*`;
        else localStorage.removeItem('debug');

        console.log('Please reload the application to apply changes.');
    };
}


// Initialize various subsystems and render the top-level React component or an
// error page if initialization fails.
let el;
try {
    console.log(`Starting ${npm_package_name} version ${npm_package_version}${GIT_VERSION ? `, git revision ${GIT_VERSION}` : ''}, built on ${BUILD_DATE}`);
    initDebugging('lost');
    el = <Main/>;
} catch(error) {
    console.error(error);
}

// Let the script embedded in the DOM know that we're taking over
(window as any).lostRunning = true;
ReactDOM.createRoot(document.getElementById("lost-container")!).render(el);
