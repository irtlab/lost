import React from 'react';
import { Link } from 'react-router-dom';
import { Navbar, Container, Nav } from 'react-bootstrap';

const NavBar = () => (
    <Navbar id='lost-navbar' data-bs-theme="dark" variant="dark" bg='dark'>
        <Container fluid>
            <Navbar.Brand as={Link} to='/'>LoST Resolver</Navbar.Brand>
            <Nav className="me-auto">
                <Nav.Link href="#images">Images</Nav.Link>
                <Nav.Link href="#features">Features</Nav.Link>
          </Nav>
        </Container>
    </Navbar>
);

export default NavBar;
