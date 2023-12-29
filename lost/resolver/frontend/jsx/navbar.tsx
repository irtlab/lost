import React from 'react';
import { NavLink } from 'react-router-dom';


const NavBar = () => (
    <div className="d-flex flex-column flex-shrink-0 p-3 text-bg-dark" style={{ width: '200px' }}>
        <a href="/" className="d-flex align-items-center mb-3 mb-md-0 me-md-auto text-white text-decoration-none">
            <span className="fs-4">
                LoST Resolver
            </span>
        </a>
        <hr/>
        <ul className="nav nav-pills flex-column mb-auto">
            <li className="nav-item">
                <NavLink className="nav-link text-white" to='/'>
                    Home
                </NavLink>
            </li>
            <li>
                <NavLink className="nav-link text-white" to='import'>
                    Import
                </NavLink>
            </li>
            <li>
                <NavLink className="nav-link text-white" to='images'>
                    Images
                </NavLink>
            </li>
            <li>
                <NavLink className="nav-link text-white" to='features'>
                    Features
                </NavLink>
            </li>
        </ul>
    </div>
);

export default NavBar;
