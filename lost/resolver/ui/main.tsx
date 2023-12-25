import React from 'react';
import 'bootstrap';
import 'bootstrap/dist/css/bootstrap.css';
import ReactDOM from 'react-dom';
import { DndProvider } from 'react-dnd';
import { TouchBackend } from 'react-dnd-touch-backend';
import { BrowserRouter as Router } from "react-router-dom";
import NavBar from "./navbar";

import './style.css';


// The following global variables are generated for us by the build system (Webpack)
declare global {
    const NODE_ENV            : string | undefined;
    const GIT_VERSION         : string | undefined;
    const BUILD_DATE          : string | undefined;
    const npm_package_name    : string | undefined;
    const npm_package_version : string | undefined;
}

function App() {
    return (        
        <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
            <NavBar/>
        </div>
    );
}


function Main() {
    return (
        <Router>
            <DndProvider backend={TouchBackend} options={{ enableMouseEvents: true }}>
                <App/>
            </DndProvider>
        </Router>
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
ReactDOM.render(el, document.getElementById('lost-container'));