from __future__ import annotations
import sys
import glob
import click
import lxml.objectify
import lxml.etree
from psycopg_pool import ConnectionPool
from datetime import datetime, timedelta
from psycopg.types.json import Jsonb
from lxml.etree import Element, SubElement, XML
from abc import ABC, abstractmethod
from flask import Flask, request, Response, current_app
from flask_cors import CORS
from . import GML_NAMESPACE, LOST_NAMESPACE, XML_NAMESPACE, NAMESPACE_MAP, LOST_MIME_TYPE, SRS_URN
from .errors import (LoSTError, BadRequest, NotFound, LocationProfileUnrecognized,
    NotImplemented, GeometryNotImplemented, SRSInvalid)
from .geometry import Point
from . import db
from .osm import extract_boundary
from . import osm
from .guid import GUID
import json
import requests


# Instances of LoST servers for various coodinate systems, e.g., geodetic-2d and
# civic.
lost_server: dict[str, LoSTServer] = dict()


class LoSTServer(ABC):
    '''An abstract LoST server base class

    This class is not meant to be instantiated directly. It just provides an
    interface that all address-type-specific LoST server implementations must
    provide.

    Instantiate GeographicLoSTServer or CivicLostServer instead.
    '''
    def __init__(self, server_id, db: ConnectionPool, table, redirect=False):
        self.server_id = server_id
        self.db = db
        self.table = table
        self.redirect = redirect

    @abstractmethod
    def check_authority(self, req: lxml.objectify.ObjectifiedElement):
        raise NotImplemented('Checking authority area is not implemented')

    @abstractmethod
    def findService(self, req: lxml.objectify.ObjectifiedElement):
        raise NotImplemented('<findService> not implemented')

    @abstractmethod
    def findIntersect(self, req: lxml.objectify.ObjectifiedElement):
        raise NotImplemented('<findIntersect> not implemented')


def serviceBoundary(value: str, gml_ns=GML_NAMESPACE, profile="geodetic-2d"):
    '''Convert ST_AsGML output to a service boundary object

    This function constructs a serviceBoundary XML element tree from the output
    generated by PostGIS' ST_AsGML function. ST_AsGML should be configured to
    generate GML version 3 using the standard namespace prefix "gml", for
    example: ST_AsGML(3, shape, 5, 17)

    Since ST_AsGML does not declare the gml namespace, we need to create a new
    root element here and declare the namespace there. Otherwise, lxml would not
    be able to parse the output of ST_AsGML.
    '''

    parser = lxml.etree.XMLParser(remove_blank_text=True)
    return XML(f'''
        <serviceBoundary profile="{profile}" xmlns:gml="{gml_ns}">
            {value}
        </serviceBoundary>''', parser)


class GeographicLoSTServer(LoSTServer):
    def __init__(self, server_id, db: ConnectionPool, table, authoritative, redirect):
        super().__init__(server_id, db, table, redirect=redirect)
        self.server_id = server_id
        self.db = db
        self.table = table
        self.authoritative = authoritative

    def check_authority(self, req: lxml.objectify.ObjectifiedElement):
        pass
    

    # def check_authority(self, req: lxml.objectify.ObjectifiedElement):
    #     with self.db.connection() as con:
    #         cur = con.execute('''
    #             SELECT ST_Intersects(geometries, ST_GeomFromText(%s, 4326)) FROM shape WHERE uri=%s
    #         ''', (p, self.authoritative))
    #         row = cur.fetchone()
    #         if row is None:
    #             raise ServerError('Server configuration error, authoritative URI not found')

    #         if not row[0]:
    #             raise NotAuthoritative('The point is outside the servers area of responsibility')

    def findIntersect(self, req: lxml.objectify.ObjectifiedElement):
        service = req.service.text
        if service is not None:
            service = service.strip()

        geom = req.interest.getchildren()[0]

        if geom.attrib.get('srsName') != SRS_URN:
            raise SRSInvalid('Unsupported SRS name')

        with self.db.connection() as con:
            cur = con.execute('''
                SELECT m.id, m.srv, m.updated, m.attrs, ST_AsGML(3, s.geometries, 5, 17)
                FROM   server.mapping AS m JOIN shape AS s ON m.shape=s.id
                WHERE  ST_Intersects(s.geometries, ST_GeomFromGML(%s))
                    and m.srv = %s''',
                (lxml.etree.tostring(geom).decode('UTF-8'), service))

            row = cur.fetchone()

        if row is None:
            raise NotFound('No suitable mapping found')

        id, service, updated, attrs, shape = row

        res = Element(f'{{{LOST_NAMESPACE}}}findIntersectResponse', nsmap=NAMESPACE_MAP)
        mapping = SubElement(res, 'mapping',
            source=self.server_id,
            sourceId=str(id),
            lastUpdated=updated.isoformat(),
            expires=(datetime.now() + timedelta(days=1)).isoformat())

        if 'displayName' in attrs:
            dn = SubElement(mapping, 'displayName')
            dn.set(f'{{{XML_NAMESPACE}}}lang', 'en')
            dn.text = attrs['displayName']

        SubElement(mapping, 'service').text = service
        mapping.append(serviceBoundary(shape))

        for uri in attrs.get('uri', []):
            SubElement(mapping, 'uri').text = uri

        return res

    def findService(self, req: lxml.objectify.ObjectifiedElement):
        service = req.service.text
        if service is not None:
            service = service.strip()

        geom = req.location.getchildren()[0]

        if geom.attrib.get('srsName') != SRS_URN:
            raise SRSInvalid('Unsupported SRS name')

        if geom.tag != f'{{{GML_NAMESPACE}}}Point':
            raise GeometryNotImplemented(f'Unsupported geometry type {geom.tag}')

        lat, lon = (geom.pos.text or '').strip().split()
        p = f'Point({lon} {lat})'
        with self.db.connection() as con:
            cur = con.execute('''
                SELECT m.id, m.srv, m.updated, m.attrs, ST_AsGML(3, s.geometries, 5, 17) AS shape
                FROM   server.mapping AS m JOIN shape AS s ON m.shape=s.id
                WHERE  ST_Contains(s.geometries, ST_GeomFromText(%s, 4326))
                    and m.srv = %s''',
                (p, service))

            row = cur.fetchone()
        
        if row is not None:
            attrs = row[3]
            # Not a leaf server and in redirect mode, so send redirect response
            if self.redirect:
                redirect_res = Element(f'{{{LOST_NAMESPACE}}}redirect', nsmap=NAMESPACE_MAP)
                redirect_res.set('target', attrs['uri'])
                redirect_res.set('source', self.server_id)
                redirect_res.set('message', 'Redirecting to the next more specific server.')
                return redirect_res

            # Not a leaf server in proxy mode
            else:
                next_server = attrs['uri']
                return self.proxy_request(next_server, req)

        else:
            # It is a leaf server, construct and return the findServiceResponse response
            with self.db.connection() as con:
                cur = con.execute('''
                    SELECT m.id, m.srv, m.updated, m.attrs, ST_AsGML(3, s.geometries, 5, 17) AS shape
                    FROM   server.mapping AS m JOIN shape AS s ON m.shape=s.id
                    WHERE  ST_Contains(s.geometries, ST_GeomFromText(%s, 4326))''',
                    (p,))

            row = cur.fetchone()
            
            if row is None:
                # No suitable mapping found, return an error
                error_res = Element(f'{{{LOST_NAMESPACE}}}error', nsmap=NAMESPACE_MAP)
                error_res.set('message', 'No suitable mapping found.')
                return error_res

            attrs = row[3]
            res = Element(f'{{{LOST_NAMESPACE}}}findServiceResponse', nsmap=NAMESPACE_MAP)
            mapping = SubElement(res, 'mapping', source=self.server_id, sourceId=str(row[0]), lastUpdated=row[2].isoformat(), expires=(datetime.now() + timedelta(days=1)).isoformat())

            if 'displayName' in attrs:
                dn = SubElement(mapping, 'displayName')
                dn.set(f'{{{XML_NAMESPACE}}}lang', 'en')
                dn.text = attrs['displayName']

            SubElement(mapping, 'service').text = row[1]
            mapping.append(serviceBoundary(row[4]))

            if 'uri' in attrs:
                for uri in attrs['uri']:
                    SubElement(mapping, 'uri').text = uri
            return res


    def proxy_request(self, server_uri, original_request):
        headers = {'Content-Type': 'application/lost+xml'}
        try:
            request_data = lxml.etree.tostring(original_request, pretty_print=True).decode()
            response = requests.post(server_uri, data=request_data, headers=headers)
            
            if response.status_code == 200:
                response_xml = lxml.etree.fromstring(response.content)
                response_obj = lxml.objectify.fromstring(lxml.etree.tostring(response_xml))
                return response_obj

        except Exception as e:
            error_res = Element(f'{{{LOST_NAMESPACE}}}error', nsmap=NAMESPACE_MAP)
            error_res.set('message', 'Proxy failed.')
            return error_res


class CivicLoSTServer(LoSTServer):
    def findService(self, doc):
        pass


app = Flask(__name__)
CORS(app)


def xmlify(doc) -> Response:
    lxml.objectify.deannotate(doc, cleanup_namespaces=True, xsi_nil=True)
    return Response(lxml.etree.tostring(doc, encoding='UTF-8',
        pretty_print=True, xml_declaration=True), mimetype=LOST_MIME_TYPE)


def findService(req):
    profile = req.location.attrib['profile']
    try:
        server = lost_server[profile]
        return server.findService(req)
    except KeyError as e:
        raise LocationProfileUnrecognized(f"Unsupported location profile '{profile}'") from e


def findIntersect(req):
    profile = req.interest.attrib['profile']
    try:
        server = lost_server[profile]
        return server.findIntersect(req)
    except KeyError as e:
        raise LocationProfileUnrecognized(f"Unsupported interest profile '{profile}'") from e


def getServiceBoundary(req):
    raise NotImplemented('<getServiceBoundary> not implemented')


def listServices(req):
    raise BadRequest('<listServices> not implemented')


def listServicesByLocation(req):
    raise BadRequest('<listServicesByLocation> not implemented')


@app.route("/", methods=["POST"])
def lost_request():
    if request.mimetype != LOST_MIME_TYPE:
        raise BadRequest('Unknown Content-Type')

    try:
        req = lxml.objectify.fromstring(request.data)
    except lxml.etree.XMLSyntaxError as e:
        raise BadRequest(f'XML syntax error: {e}') from e

    if not req.tag.startswith(f'{{{LOST_NAMESPACE}}}'):
        raise BadRequest('Unsupported XML namespace')

    type_ = req.tag[len(LOST_NAMESPACE) + 2:]
    if   type_ == 'findService':            res = findService(req)
    elif type_ == 'findIntersect':          res = findIntersect(req)
    elif type_ == 'getServiceBoundary':     res = getServiceBoundary(req)
    elif type_ == 'listServices':           res = listServices(req)
    elif type_ == 'listServicesByLocation': res = listServicesByLocation(req)
    else: raise NotImplemented(f'Unsupported request type "{type_}"')

    return xmlify(res)


@app.errorhandler(LoSTError)
def lost_error(exc: LoSTError):
    return xmlify(exc.to_xml(current_app.config.get('server-id', None)))


@click.group(help='LoST server', invoke_without_command=True)
@click.pass_context
@click.option('--db-url', '-d', envvar='DB_URL', help='PostgreSQL database URL')
@click.option('--max-con', type=int, default=16, envvar='MAX_CON', help='Maximum number of DB connections', show_default=True)
@click.option('--min-con', type=int, default=1, envvar='MIN_CON', help='Minimum number of free DB connections', show_default=True)
def cli(ctx, db_url, min_con, max_con):
    if db_url is None:
        print("Error: Please configure database via --db-url or environment variable DB_URL")
        sys.exit(1)

    ctx.ensure_object(dict)
    ctx.obj['db_url'] = db_url

    try:
        db.init(db_url, min_con=min_con, max_con=max_con)
    except Exception as e:
        print(f"Error while connecting to datababase '{db_url}': {e}")
        sys.exit(1)


osm.cli(cli)
db.cli(cli)


@cli.command(help='Start LoST server')
@click.option('--ip', '-i', type=str, envvar='IP', default='127.0.0.1', help='IP address to listen on', show_default=True)
@click.option('--port', '-p', type=int, envvar='PORT', default=5000, help='Port number to listen on', show_default=True)
@click.option('--geo-table', '-g', default='mapping', envvar='GEO_TABLE', help='Name of geographic mapping table', show_default=True)
@click.option('--civic-table', '-c', envvar='CIVIC_TABLE', help='Name of civic address mapping table', show_default=True)
@click.option('--server-id', '-i', default='lost-server', envvar='SERVER_ID', help='Unique ID of the LoST server', show_default=True)
@click.option('--authoritative', '-a', envvar='AUTHORITATIVE', help='URI of the shape for which the server is authoritative')
@click.option('--redirect', '-r', is_flag=True, envvar='REDIRECT', help='Send redirects instead of proxying client requests')
def start(ip, port, geo_table, civic_table, server_id, authoritative, redirect):
    global lost_server
    
    print("Instantiating a LoST server for the 'geodetic-2d' profile")
    lost_server['geodetic-2d'] = GeographicLoSTServer(server_id, db.pool, geo_table, authoritative, redirect=redirect)

    if civic_table is not None:
        print("Instantiating a LoST server for the 'civic' profile")
        lost_server['civic'] = CivicLoSTServer(server_id, db.pool, civic_table, redirect=redirect)

    app.config['server-id'] = server_id
    app.config['db'] = db.pool
    app.run(ip, port, debug=True, threaded=True, use_reloader=True)


def update_db(geometry, attrs, url_map):
        with db.pool.connection() as con:
            # Check if the geometry is already present in the database
            cur = con.execute('''
                SELECT id FROM shape
                WHERE ST_Equals(geometries, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
            ''', (Jsonb(geometry),))
            previous = cur.fetchone()

            if previous is None:
                # If the geometry is not already in the database, insert that geometry
                uri = attrs.get('uri', str(GUID()))
                cur = con.execute('''
                    INSERT INTO shape (uri, geometries, updated, attrs)
                    VALUES (%s, ST_ForceCollection(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), %s, %s)
                    RETURNING id
                ''', (uri, Jsonb(geometry), attrs['timestamp'], Jsonb(attrs)))
                
                shape_id = cur.fetchone()[0]
            else:
                shape_id = previous[0]

            uri = attrs.get('uri')
            if uri is not None and url_map is not None:
                server_uri = url_map.get(uri)

                con.execute('''
                    DELETE FROM server.mapping
                    WHERE srv='lost' and (shape IS NULL or SHAPE=%s)
                ''', (shape_id,))

                if server_uri is not None:
                    cur = con.execute('''
                        INSERT INTO server.mapping (shape, srv, attrs)
                        VALUES (%s, %s, %s)
                    ''', (shape_id, 'lost', Jsonb({ 'uri': server_uri })))


@cli.command(help='Load GeoJSON geometries from files matching <matching> into the database.')
@click.option('--url-map', '-u', envvar='URL_MAP', help='JSON file with URL map')
@click.argument('pattern')
def load(pattern, url_map):
    if url_map is not None:
        click.echo(f'Loading URL map from {url_map}')
        with open(url_map, 'r') as file:
            url_map = json.load(file)

    # For each GeoJSON file in the folder, insert the geometry into the database
    for filename in glob.glob(pattern):
        click.echo(f'Loading {filename}...', nl=False)
        try:
            with open(filename, 'r') as file:
                geojson = json.load(file)

            geometry, attrs = extract_boundary(geojson)
            update_db(geometry, attrs, url_map)
        finally:
            click.echo('done.')

                    
if __name__ == '__main__':
    cli()