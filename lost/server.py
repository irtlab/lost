from __future__ import annotations
import sys
import os
import click
import psycopg2
import psycopg2.extras
import psycopg2.errors
import lxml.objectify
import lxml.etree
import uuid
import base64
from datetime import datetime, timedelta
from lxml.etree import Element, SubElement, XML
from collections import namedtuple
from abc import ABC, abstractmethod
from psycopg2.pool import ThreadedConnectionPool
from flask import Flask, request, abort, Response
from werkzeug.exceptions import BadRequest
from contextlib import contextmanager
from flask_cors import CORS


MIME_TYPE      = 'application/lost+xml'
LOST_NAMESPACE = 'urn:ietf:params:xml:ns:lost1'
GML_NAMESPACE  = 'http://www.opengis.net/gml'
XML_NAMESPACE  = 'http://www.w3.org/XML/1998/namespace'
NAMESPACE_MAP  = {
    None: LOST_NAMESPACE,
    'gml': GML_NAMESPACE,
    'xml': XML_NAMESPACE
}


# Add support for serialization and deserialization of JSON columns
psycopg2.extensions.register_adapter(dict, psycopg2.extras.Json)


# Create a pool of persistent PostgreSQL database connections. When we are done
# with a PostgreSQL connection, we simply return it to the pool without closing
# the connection. This helps avoid the need to open a new database connection
# for every request.
db_connection_pool: ThreadedConnectionPool


# Instances of LoST servers for various coodinate systems, e.g., geodetic-2d and
# civic.
lost_server: dict[str, LoSTServer] = dict()


class PQLogger:
    '''Log PostgreSQL warnings to standard output.

    Instances of this class are assigned to the notices property on psycopg2
    connections and print any warnings received from the PostgreSQL database to
    the standard output.
    '''
    def append(self, message):
        print(message.strip())


class GUID(object):
    '''A globally unique identifier.

    A custom implementation of a globally unique identifier. Backed by UUID
    version 4 (randomly generated) with a base64 string representation.
    '''
    def __init__(self, v):
        if v is None:
            self.value = uuid.uuid4()
        elif isinstance(v, uuid.UUID):
            self.value = v
        elif isinstance(v, GUID):
            self.value = v.value
        elif isinstance(v, str):
            if len(v) == 22:
                self.value = uuid.UUID(bytes=base64.urlsafe_b64decode(f'{v}=='), version=4)
            else:
                self.value = uuid.UUID('{%s}' % v)
        else:
            raise Exception('Unsupported GUID value representation')

    def __str__(self):
        return base64.urlsafe_b64encode(self.value.bytes)[:-2].decode('ascii')

    def __eq__(self, obj):
        return self.value == obj.value

    def getquoted(self):
        '''Serialization support for psycopg2.'''
        return f"'{self.value}'::uuid".encode('UTF-8')

    def __conform__(self, proto):
        '''Serialization support for psycopg2.'''
        if proto is psycopg2.extensions.ISQLQuote:
            return self


def recreate_guid_from_psycopg():
    '''Re-create GUID objects from PostgreSQL UUID oids.

    When PostgreSQL gives us UUID data, we convert it to instances of GUID
    objects rather than the standard uuid object.
    '''
    ext = psycopg2.extensions
    t1 = ext.new_type((2950, ), "GUID",
            lambda data, cursor: data and GUID(data) or None)
    t2 = ext.new_array_type((2951,), "GUID[]", t1)

    ext.register_type(t1)
    ext.register_type(t2)

# When loading data from Psycopg, create GUID objects for UUID data
recreate_guid_from_psycopg()

# Add support for serialization and deserialization of JSON columns
psycopg2.extensions.register_adapter(dict, psycopg2.extras.Json)



def find_connection(uid=None) -> psycopg2.connection:
    '''Retrieve a working (connected) connection from pool.

    If a connection is shutdown administratively on the PostgreSQL server, the
    connection pool may return a connection that is no longer connected and that
    will raise an exception when the client attempts to use it. Since we need to
    set a variable containing the uid of the authorized user at the beginning of
    the connection, we use that step to detect whether the connection retrieved
    from the pool is connected (the operation will fail if not). If we get a
    disconnected connection, we repeat the step. If we need to repeat more times
    than maxconn of the connection pool, no working connection can be retrieved.
    '''
    for i in range(db_connection_pool.maxconn + 1):
        db = db_connection_pool.getconn()
        db.notices = PQLogger()
        db.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_SERIALIZABLE)
        try:
            # If we have a uid, set the session.uid variable to it, otherwise
            # reset the variable.
            cur = db.cursor()
            if uid is not None:
                cur.execute('set session.uid=%s', (uid,))
            else:
                cur.execute('reset session.uid')

            # If setting/resetting the variable succeeded, this is a working
            # connection and we can return it to the caller.
            return db
        except (psycopg2.errors.AdminShutdown, psycopg2.InterfaceError) as e:
            # On an exception, put the connection back to the pool and re-try if
            # we have any loop iterations left.
            db_connection_pool.putconn(db)
        finally:
            # Close the temporary cursor used to set/reset the session.uid
            # variable if we have one.
            if cur:
                cur.close()
    else:
        # If we need to iterate more times than the size of the connection pool,
        # we cannot get a working connection from the pool and must raise an
        # exception.
        raise Exception("Couldn't get usable PostgreSQL connection from the pool")


@contextmanager
def db_cursor():
    db = find_connection()
    try:
        with db:
            with db.cursor() as cur:
                yield cur
    finally:
        db_connection_pool.putconn(db)


# The order of coordinate axes across various standards is as follows:
# GeoJSON:            [lon, lat]
# PostGIS (WKT, WKB): [lon, lat]
# KML:                [lon, lat]
# EPSG:4326           [lat, lon]
# GML:                [lat, lon]
Point = namedtuple('Point', ['lon', 'lat'])


class LoSTServer(ABC):
    '''An abstract LoST server base class

    This class is not meant to be instantiated directly. It just provides an
    interface that all address-type-specific LoST server implementations must
    provide.

    Instantiate GeographicLoSTServer or CivicLostServer instead.
    '''
    def __init__(self, server_id, table):
        self.server_id = server_id
        self.table = table

    @abstractmethod
    def find_service(self, req: lxml.objectify.ObjectifiedElement):
        pass


def service_boundary(value: str, gml_ns=GML_NAMESPACE, profile="geodetic-2d"):
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
    def find_point(self, service, point: Point):
        with db_cursor() as db:
            db.execute('''
                SELECT m.id, m.service, m.modified, m.attrs, ST_AsGML(3, s.geometries, 5, 17)
                FROM   mapping AS m JOIN shape AS s ON m.shape=s.id
                WHERE  ST_Contains(s.geometries, ST_GeomFromText(%s, 4326))''',
                (f'Point({point.lon} {point.lat})',))

            id, service, modified, attrs, shape = db.fetchone()

        res = Element(f'{{{LOST_NAMESPACE}}}findServiceResponse', nsmap=NAMESPACE_MAP)
        mapping = SubElement(res, 'mapping',
            source=self.server_id,
            sourceId=str(id),
            lastUpdated=modified.isoformat(),
            expires=(datetime.now() + timedelta(days=1)).isoformat())

        if 'displayName' in attrs:
            dn = SubElement(mapping, 'displayName')
            dn.set(f'{{{XML_NAMESPACE}}}lang', 'en')
            dn.text = attrs['displayName']

        SubElement(mapping, 'service').text = service
        mapping.append(service_boundary(shape))

        for uri in attrs.get('uri', []):
            SubElement(mapping, 'uri').text = uri

        return res

    def find_service(self, req: lxml.objectify.ObjectifiedElement):
        service = req.service.text
        if service is not None:
            service = service.strip()

        geom = req.location.getchildren()[0]
        if geom.tag == f'{{{GML_NAMESPACE}}}Point':
            lat, lon = (geom.pos.text or '').strip().split()
            return self.find_point(service, Point(lon, lat))
        else:
            raise BadRequest('Unsupported geometry type')


class CivicLoSTServer(LoSTServer):
    def find_service(self, doc):
        pass


app = Flask(__name__)
CORS(app)


@app.route("/", methods=["GET"])
def ping():
    with db_cursor() as db:
        db.execute("SELECT NOW()")
        res = db.fetchone()
        return f"Database says: {res[0]}"


@app.route("/", methods=["POST"])
def submit():
    if request.mimetype != MIME_TYPE:
        abort(400, 'Unsupported content type')

    req = lxml.objectify.fromstring(request.data)

    if req.tag == f"{{{LOST_NAMESPACE}}}findService":
        profile = req.location.attrib['profile']
        try:
            server = lost_server[profile]
        except KeyError:
            abort(400, f"Unsupported location profile '{profile}'")

        res = server.find_service(req)
        lxml.objectify.deannotate(res, cleanup_namespaces=True, xsi_nil=True)
        return Response(lxml.etree.tostring(res, encoding='UTF-8',
            pretty_print=True, xml_declaration=True), mimetype=MIME_TYPE)
    else:
        abort(400, f'Unsupported request type "{req.tag}"')


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    try:
        if ctx.invoked_subcommand is None:
            ctx.invoke(start)
    except KeyboardInterrupt:
        pass
    pass


@cli.command()
@click.option('--port', '-p', type=int, help='Port number to listen on.')
@click.option('--db-url', '-d', help='PostgreSQL database URL')
@click.option('--max-con', default=16, help='Maximum number of DB connections', show_default=True)
@click.option('--min-con', default=1, help='Minimum number of free DB connections', show_default=True)
@click.option('--geo-table', default='geo', help='Name of geographic mapping table', show_default=True)
@click.option('--civic-table', default='civic', help='Name of civic address mapping table', show_default=True)
@click.option('--server-id', default='lost-server', help='Unique ID of the LoST server', show_default=True)
def start(port, db_url, max_con, min_con, geo_table, civic_table, server_id):
    global db_connection_pool, lost_server

    if db_url is None:
        try:
            db_url = os.environ['DB_URL']
        except KeyError:
            print("Error: Please configure database via --db-url or environment variable DB_URL")
            sys.exit(1)

    try:
        # ThreadedConnection pool will attempt to connect to the database. If
        # the attempt fails, an exception will be raised. We catch the exception
        # and print an informative message. This will allow us to fail early if
        # the database is unavailable and not later when the first request
        # arrives.
        db_connection_pool = ThreadedConnectionPool(min_con, max_con, db_url)
    except Exception as e:
        print(f"Error while connecting to datababase '{db_url}': {e}")
        sys.exit(1)

    if port is None:
        port = int(os.environ.get("PORT", 5000))

    if geo_table != None:
        print("Instantiating a LoST server for the 'geodetic-2d' profile")
        lost_server['geodetic-2d'] = GeographicLoSTServer(server_id, geo_table)

    if civic_table != None:
        print("Instantiating a LoST server for the 'civic' profile")
        lost_server['civic'] = CivicLoSTServer(server_id, civic_table)

    app.run('0.0.0.0', port, debug=True, threaded=True)


@cli.command('init-db')
@click.option('--db-url', '-d', help='PostgreSQL database URL')
@click.option('--drop', '-D', default=False, is_flag=True, help='Drop tables if they exist first')
def init_db(db_url, drop):
    if db_url is None:
        try:
            db_url = os.environ['DB_URL']
        except KeyError:
            print("Error: Please configure database via --db-url or environment variable DB_URL")
            sys.exit(1)

    with psycopg2.connect(db_url) as db:
        cur = db.cursor()
        if drop:
            print("Dropping modification trigger on table mapping")
            cur.execute('DROP TRIGGER IF EXISTS update_modification_timestamp ON mapping')

            print("Dropping table mappping")
            cur.execute('DROP TABLE IF EXISTS mapping')

            print("Dropping function update_modification_timestamp()")
            cur.execute('DROP FUNCTION IF EXISTS update_modification_timestamp()')

        print("Creating function update_modification_timestamp()")
        cur.execute('''
            CREATE FUNCTION public.update_modification_timestamp() RETURNS trigger
                LANGUAGE plpgsql
                AS $$
            begin
                NEW.modified = now();
                return NEW;
            end;
            $$;
        ''')

        print("Creating table mapping")
        cur.execute('''
            CREATE TABLE mapping (
                id       uuid         PRIMARY KEY DEFAULT uuid_generate_v4(),
                service  text         NOT NULL,
                shape    uuid         references shape(id) ON DELETE SET NULL,
                created  timestamptz  DEFAULT now() NOT NULL,
                modified timestamptz  DEFAULT now() NOT NULL,
                attrs    jsonb        NOT NULL DEFAULT '{}'::jsonb
            )''')

        print("Creating modification trigger on table mapping")
        cur.execute('''
            CREATE TRIGGER update_modification_timestamp BEFORE UPDATE ON mapping FOR EACH ROW EXECUTE FUNCTION public.update_modification_timestamp();
        ''')

if __name__ == '__main__':
    cli()