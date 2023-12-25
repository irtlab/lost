import os
import math
import urllib.request
import numpy as np
import skimage.io
import requests
import json
import time
import random
import osm2geojson
import urllib.request
import flask

from flask_marshmallow    import Marshmallow
from werkzeug.exceptions  import BadRequest, HTTPException
from io                   import BytesIO
from flask                import abort, jsonify, request, current_app, send_from_directory, Blueprint
from base64               import b64encode
from pyproj               import Transformer
from skimage.transform    import (
    estimate_transform,
    matrix_transform,
    SimilarityTransform,
    AffineTransform,
    ProjectiveTransform,
    warp)

from marshmallow import Schema, fields as fld, ValidationError, validate

from ..guid import GUID
from .. import db as db2
from . import app

app.config['PROPAGATE_EXCEPTIONS'] = False

api = Blueprint('api', __name__, url_prefix='/api')
ma = Marshmallow(api)


@api.errorhandler(HTTPException)
def handle_error(e):
    body = {
        'code'        : e.code,
        'reason'      : e.name,
        'description' : e.description
    }

    original = getattr(e, 'original_exception', None)
    if original:
        body['detail'] = getattr(original, 'messages', None) or str(original)

    indent = None
    separators = (",", ":")

    if current_app.config.get("JSONIFY_PRETTYPRINT_REGULAR", None) or current_app.debug:
        indent = 2
        separators = (", ", ": ")

    response = e.get_response()
    response.data = flask.json.dumps(body, sort_keys=False, indent=indent, separators=separators)
    response.content_type = 'application/json'
    return response


@api.errorhandler(ValidationError)
def failed_validation(e):
    exc = BadRequest('Invalid or missing JSON body')
    exc.original_exception = e
    return handle_error(exc)


def validate_bounds(bounds):
    if not isinstance(bounds, list):
        raise Exception('Bounds must be a list')

    if len(bounds) != 4:
        raise Exception('Bounds must have 4 values (%d found)' % len(bounds))

    b = map(lambda v: float(v), bounds)

    if (not (-180 < b[0] < 180)) or (not (b[0] < b[2] < 180)):
        raise Exception('Invalid longitude value')

    if (not (-85 < b[1] < 85)) or (not (b[1] < b[3] < 85)):
        raise Exception('Invalid latitude value')

    return b


def parse_coordinates(coordinates):
    if isinstance(coordinates, list):
        return [coordinates[0], coordinates[1]]

    a, b = coordinates.get('x', None), coordinates.get('y', None)
    if a is not None and b is not None:
        return [a, b]

    a, b = coordinates.get('lng', None), coordinates.get('lat', None)
    if a is not None and b is not None:
        return [a, b]

    raise Exception('Invalid coordinate format')


def parse_control_links(links):
    if type(links) != list:
        raise Exception('Invalid or missing control links (must be array)')

    a = []
    b = []
    for link in links:
        a.append(parse_coordinates(link[0]))
        b.append(parse_coordinates(link[1]))

    return (a, b)


@api.route('/estimate', methods=['POST'])
def estimate():
    data = request.get_json()
    if type(data) != dict:
        abort(400, description='Invalid or missing JSON array in request body')

    try:
        a, b = parse_control_links(data['controlLinks'])
    except Exception as e:
        abort(400, description='Invalid format of control links: %s' % e)

    count = len(a)
    if count < 2:
        abort(400, description='Please provide at least two control links')

    try:
        a = np.array(a).reshape((count, 2))
        b = np.array(b).reshape((count, 2))
    except ValueError as e:
        abort(400, description='Invalid control link format')

    if count == 2:
        method = 'similarity'
    elif count == 3:
        method = 'affine'
    else:
        method = 'projective'

    tform = estimate_transform(method, a, b)

    if not np.allclose(tform.inverse(tform(a)), a):
        abort(500, description='Could not estimate transformation parameters')

    return jsonify({
        'forward' : tform.params.tolist(),
        'backward': tform._inv_matrix.tolist()
    })


@api.route("/reproject", methods=['POST'])
def reproject():
    data = request.get_json()
    if type(data) != dict:
        abort(400, description='Invalid or missing JSON object in request body')

    url = data.get('url', None)
    if type(url) != str:
        abort(400, description='Invalid or missing url attribute')

    try:
        if url.startswith('data:'):
            image = skimage.io.imread(urllib.request.urlopen(url))
        else:
            image = skimage.io.imread(url)
    except Exception as e:
        abort(400, description='Invalid URL')

    height, width, _ = image.shape
    corners = np.array([[0, 0], [width - 1, height - 1], [width - 1, 0], [0, height - 1]])

    try:
        a, b = parse_control_links(data['controlLinks'])
    except Exception as e:
        abort(400, description='Invalid format of control links: %s' % e)

    count = len(a)
    if count < 2:
        abort(400, description='Please provide at least two control links')

    try:
        a = np.array(a).reshape((count, 2))
        b = np.array(b).reshape((count, 2))
    except ValueError as e:
        abort(400, description='Invalid control link format')

    # Assume the coordinates are Cartesian. Cartesian coordinates have the
    # origin in the bottom right corner. Thus, we need to subtract the y
    # coordinate from the image's height to move the origin to the upper left
    # corner of the image to match the image's coordinate system.
    a = [[v[0], height - v[1] - 1] for v in a]

    transformer = Transformer.from_crs('epsg:4326', 'epsg:3857')
    b3857 = [[*transformer.transform(c[1], c[0])] for c in b]

    if count == 2:
        method = 'similarity'
    elif count == 3:
        method = 'affine'
    else:
        method = 'projective'

    # Estimate the transformation from source coordinates (x,y) to destination
    # coordinates in Web Mercator (EPSG:3857)
    project = estimate_transform('projective', np.array(a), np.array(b3857))

    # Project the image's corners into Web Mercator
    projected_corners = matrix_transform(corners, project.params)

    # Find out the coordinates for the bounding box in the Web Mercator reference
    # frame.
    min_lng = min([c[0] for c in projected_corners])
    min_lat = min([c[1] for c in projected_corners])
    max_lng = max([c[0] for c in projected_corners])
    max_lat = max([c[1] for c in projected_corners])

    # Calculate the scaling factor so that the transformed floorplan fits into the
    # original dimensions of the input image.
    dx = max_lng - min_lng
    dy = max_lat - min_lat
    xscale = width / dx
    yscale = height / dy
    scale = xscale if xscale < yscale else yscale

    shift = SimilarityTransform(translation=(-min_lng, -min_lat))
    scale = SimilarityTransform(scale=scale)
    flip = AffineTransform(matrix=np.array([[1, 0, 0], [0, -1, height - 1], [0, 0, 1]]))

    # Build a transformation that brings the transformed image in WebMercator back
    # into the dimensions of the input image. The transformed image will be properly
    # shifted and scaled to fill the dimensions of the input image. We also need to
    # flip the image along the x axis because because the y axis and the latitude
    # axis grow in opposite directions.
    fit = flip.params @ scale.params @ shift.params

    # Now calculate the dimensions of the output (preview) image
    w, h = matrix_transform([max_lng, min_lat], fit)[0]
    w = math.ceil(w)
    h = math.ceil(h)

    project_and_fit = ProjectiveTransform(matrix=fit @ project.params)

    # and warp the input image to generate a preview image that can be overlaid over
    # a map
    preview = warp(image, project_and_fit.inverse, output_shape=(h, w))

    # Generate bounds in WGS84
    project_wgs84 = estimate_transform(method, np.array(a), np.array(b))
    bounds = matrix_transform([[0, 0], [w - 1, h - 1]], project_wgs84.params @ project_and_fit._inv_matrix)

    buffer = BytesIO()
    skimage.io.imsave(buffer, preview, plugin='pil', format_str='PNG')

    return jsonify({
        'bounds': [
            {'lng': bounds[0][0], 'lat': bounds[0][1]},
            {'lng': bounds[1][0], 'lat': bounds[1][1]}
        ],
        'url': 'data:image/png;base64,%s' % b64encode(buffer.getvalue()).decode('ascii')
    })


class RasterImageSchema(Schema):
    id           = fld.Integer()
    name         = fld.Str(required=True, validate=validate.Length(min=1))
    url          = fld.Str(required=True, validate=validate.URL())
    width        = fld.Integer(required=True, validate=validate.Range(min=0))
    height       = fld.Integer(required=True, validate=validate.Range(min=0))
    size         = fld.Integer(required=True, validate=validate.Range(min=0))
    uploaded     = fld.DateTime()
    fileName     = fld.Str(required=True, validate=validate.Length(min=1))
    lastModified = fld.DateTime()
    storageRef   = fld.Str(required=True, validate=validate.Length(min=1))


def _select_images(db, id=None):
    return db.execute(f'''
        select
            id, name, url, width, height, size, uploaded,
            file_name     as "fileName",
            last_modified as "lastModified",
            storage_ref   as "storageRef"
        from raster_image
        {id and 'where id=%s' or ''}
    ''', (id,))


@api.route('/image', methods=['GET'])
def get_all_images():
    with db2.pool.connection() as con:
        cur = _select_images(con)
        return jsonify(cur.fetchall())


@api.route('/image', methods=['PUT'])
def replace_all_images():
    data = RasterImageSchema(many=True).load(request.get_json())
    recs = []

    with db2.pool.connection() as con:
        cur = con.execute('delete from raster_image')
        if len(data):
            recs = execute_values(cur, '''
                insert into raster_image
                    (id, name, file_name, height, last_modified,
                    size, storage_ref, uploaded, url, width)
                values %s
                returning
                    id, name, url, width, height, size, uploaded,
                    file_name     as "fileName",
                    last_modified as "lastModified",
                    storage_ref   as "storageRef"
            ''', data, template='''
                (%(id)s, %(name)s, %(fileName)s, %(height)s, %(lastModified)s,
                %(size)s, %(storageRef)s, %(uploaded)s, %(url)s, %(width)s)
            ''', fetch=True)
    return jsonify(recs)


@api.route('/image', methods=['DELETE'])
def delete_all_images(id):
    with db2.pool.connection() as con:
        con.execute('delete from raster_image')
    return '', 204


@api.route('/image/<int:id>', methods=['GET'])
def get_image(id):
    with db2.pool.connection() as con:
        data = _select_images(con, id).fetchone()
        return jsonify(data) if data else abort(404)


@api.route('/image/<int:id>', methods=['PUT'])
def update_image(id):
    data = RasterImageSchema().load(request.get_json())
    if data['id'] != id:
        abort(400, description='Invalid object id')

    with db2.pool.connection() as con:
        cur = con.execute('''
            insert into raster_image (
                id, name, file_name, height, last_modified,
                size, storage_ref, uploaded, url, width
            ) values (
                %(id)s, %(name)s, %(fileName)s, %(height)s, %(lastModified)s,
                %(size)s, %(storageRef)s, %(uploaded)s, %(url)s, %(width)s
            ) on conflict (id) do update set
                name          = %(name)s,
                file_name     = %(fileName)s,
                height        = %(height)s,
                last_modified = %(lastModified)s,
                size          = %(size)s,
                storage_ref   = %(storageRef)s,
                uploaded      = %(uploaded)s,
                url           = %(url)s,
                width         = %(width)s
            returning
                id, name, url, width, height, size, uploaded,
                file_name     as "fileName",
                last_modified as "lastModified",
                storage_ref   as "storageRef"
        ''', data)
        data = cur.fetchone()
        return jsonify(data) if data else abort(404)


@api.route('/image/<int:id>', methods=['DELETE'])
def delete_image(id):
    with db2.pool.connect() as con:
        con.execute('''
            delete from raster_image
            where id=%s
        ''', (id,))
        return '', 204


class ControlPointSchema(Schema):
    id          = fld.Integer()
    type        = fld.Str(required=True, validate=validate.Equal("Point"))
    coordinates = fld.List(fld.Number, required=True, validate=validate.Length(min=2, max=3))
    crs         = fld.Dict()
    crsFeature  = fld.Str()


def _select_control_points(db, id=None):
    return db.execute(f"""
        select
            id,
            'Point' as type,
            ST_AsGeoJSON(coordinates)::json->'coordinates' as coordinates
        from control_point
        { id and 'where id=%s' or '' }
    """, (id,))


@api.route('/control_point', methods=['GET'])
def get_all_control_points():
    with db2.pool.connection() as con:
        return jsonify(_select_control_points(con).fetchall())


def parse_geojson_crs(gjson):
    crs = gjson.get('crs', None)
    if type(crs) != dict:
        raise Exception('Missing or malformed crs attribute')

    if crs.get('type', None) != 'name':
        raise Exception('Unsupported CRS type')

    props = crs.get('properties', {})

    name = props.get('name', None)
    if type(name) != str:
        raise Exception('Invalid crs name')

    return name


def parse_geojson(gjson):
    id = gjson['id']
    crs = parse_geojson_crs(gjson)

    # If the crs GeoJSON attribute contains a custom name starting with
    # "feature:", set the CRS name to "EPSG:0" to indicate to PostgresSQL
    # that the geometry has no coordinate reference. When included in a
    # geospatial query, such object will generate a query exception in
    # PostgreSQL. Custom server-side functions need to be invoked to
    # convert such geometry to WGS 84.

    if crs.startswith('feature:'):
        crs_feature = GUID(crs[8:])
        crs_name = 'EPSG:0'
    else:
        crs_feature = None
        crs_name = crs

    rest = dict(gjson)
    del rest['id']
    rest['crs'] = {
        'type': 'name',
        'properties': {
            'name': crs_name }}

    return (id, json.dumps(rest))


@api.route('/control_point', methods=['PUT'])
def replace_all_control_points():
    recs = []
    data = ControlPointSchema(many=True).load(request.get_json())

    # We get the point in GeoJSON format from the client. Extract the id and stringify
    # the rest of the point so that it can be passed to ST_GeomFromGeoJSON.
    data = [parse_geojson(d) for d in data]

    with db2.pool.connection() as con:
        con.execute('delete from control_point')
        if len(data):
            recs = execute_values(con, '''
                insert into control_point
                    (id, coordinates)
                values %s
                returning
                    id,
                    'Point' as type,
                    ST_AsGeoJSON(coordinates)::json->'coordinates' as coordinates
            ''', data, template='''(
                %s,
                ST_GeomFromGeoJSON(%s)
            )''', fetch=True)
    return jsonify(recs)


@api.route('/control_point', methods=['DELETE'])
def delete_all_control_points(id):
    with db2.pool.connection() as con:
        con.execute('delete from control_point')
    return '', 204


class ShapeSchema(Schema):
    id         = fld.Integer()
    type       = fld.Str(required=True, validate=validate.Equal("GeometryCollection"))
    geometries = fld.List(fld.Dict, required=True)


def _select_shapes(db, id=None):
    return db.execute(f"""
        select
            id,
            'GeometryCollection' as type,
            ST_AsGeoJSON(geometries)::json->'geometries' as geometries
        from shape
        { id and 'where id=%s' or '' }
    """, (id,))


@api.route('/shape', methods=['GET'])
def get_all_shapes():
    with db2.pool.connection() as con:
        cur = _select_shapes(con)
        return jsonify(cur.fetchall())


@api.route('/shape/<int:id>', methods=['GET'])
def get_shape(id):
    with db2.pool.connection() as con:
        cur = _select_shapes(con, id)
        data = cur.fetchone()
        return jsonify(data) if data else abort(404)


@api.route('/shape', methods=['PUT'])
def replace_all_shapes():
    recs = []
    data = [(d['id'], json.dumps({
        "type"       : "GeometryCollection",
        "geometries" : d['geometries']
    })) for d in ShapeSchema(many=True).load(request.get_json())]

    with db2.pool.connection() as con:
        con.execute('delete from shape')
        if len(data):
            recs = execute_values(con, '''
                insert into shape
                    (id, geometries)
                values %s
                returning
                    id,
                    'GeometryCollection' as type,
                    ST_AsGeoJSON(geometries)::json->'geometries' as geometries
            ''', data, template='''(
                    %s,
                    ST_GeomFromGeoJSON(%s)
            )''', fetch=True)
    return jsonify(recs)


@api.route('/shape', methods=['DELETE'])
def delete_all_shapes(id):
    with db2.pool.connection() as con:
        con.execute('delete from shape')
    return '', 204


class DeviceSchema(Schema):
    id           = fld.Integer()
    name         = fld.Str(required=True, validate=validate.Length(min=1))
    center       = fld.List(fld.Number)
    created      = fld.DateTime()
    radius       = fld.Number(allow_none=True)


def _select_devices(cursor, id=None):
    cursor.execute(f"""
        select
            id,
            ST_AsGeoJSON(center)::json->'coordinates' as center
        from device
        { id and 'where id=%s' or '' }
    """, (id,))



@api.route('/device', methods=['GET'])
def get_all_devices():
    with db2.pool.connection() as con:
        cur = _select_devices(con)
        return jsonify(cur.fetchall())


@api.route('/device', methods=['PUT'])
def replace_all_devices():
    recs = []

    data = [(
        d.get('id'),
        d.get('name'),
        d.get('center') and f"point({d['center'][0]} {d['center'][1]})" or None,
        d.get('radius')
    ) for d in DeviceSchema(many=True).load(request.get_json())]

    with db2.pool.connection() as con:
        con.execute('delete from device')
        if len(data):
            recs = execute_values(con, '''
                insert into device
                    (id, name, center, radius)
                values %s
                returning
                    id,
                    name,
                    ST_AsGeoJSON(center)::json->'coordinates' as center,
                    radius
            ''', data, template='''(
                    %s,
                    %s,
                    ST_GeomFromText(%s, 4326),
                    %s
            )''', fetch=True)
    return jsonify(recs)


@api.route('/device', methods=['DELETE'])
def delete_all_devices(id):
    with db2.pool.connection() as con:
        con.execute('delete from device')
    return '', 204


class FeatureSchema(Schema):
    id            = fld.Integer()
    type          = fld.Str(required=True)
    name          = fld.Str(required=True, validate=validate.Length(min=1))
    parent        = fld.Integer(required=True, allow_none=True)
    verticalRange = fld.Str(allow_none=True)
    indoor        = fld.Boolean(required=True)
    shape         = fld.Integer(required=True, allow_none=True)
    controlPoints = fld.List(fld.Str, required=True, allow_none=True)
    created       = fld.DateTime()
    image         = fld.Integer(required=True, allow_none=True)
    transform     = fld.Str(required=True, allow_none=True)
    attrs         = fld.Dict(fld.Str, required=True)


def _select_features(db, id=None):
    return db.execute(f"""
        select
            id,
            type,
            name,
            parent,
            vertical_range as verticalRange,
            indoor,
            shape,
            control_points as controlPoints,
            created,
            image,
            transform,
            attrs
        from feature
        { id and 'where id=%s' or '' }
    """, (id,))


@api.route('/feature', methods=['GET'])
def get_all_features():
    with db2.pool.connection() as con:
        cur = _select_features(con)
        return jsonify(cur.fetchall())


@api.route('/feature', methods=['PUT'])
def replace_all_features():
    recs = []
    data = FeatureSchema(many=True).load(request.get_json())

    with db2.pool.connection() as con:
        con.execute('delete from feature')
        if len(data):
            recs = execute_values(con, '''
                insert into feature (
                    id, type, name, parent, indoor,
                    vertical_range,
                    shape, control_points, created, image, transform, attrs
                ) values %s
                returning
                    id, type, name, parent,
                    indoor, shape,
                    vertical_range as verticalRange,
                    control_points as controlPoints,
                    created, image, transform, attrs
            ''', data, template='''(
                %(id)s, %(type)s, %(name)s, %(parent)s, %(indoor)s,
                %(verticalRange)s,
                %(shape)s, %(controlPoints)s, %(created)s, %(image)s, %(transform)s, %(attrs)s
            )''', fetch=True)
    return jsonify(recs)


@api.route('/feature', methods=['DELETE'])
def delete_all_features(id):
    with db2.pool.connection() as con:
        con.execute('delete from feature')
    return '', 204


class CoordinateTransformSchema(Schema):
    id            = fld.Integer()
    controlLinks  = fld.Dict(fld.Str, required=True)
    toWGS84       = fld.Str(allow_none=True)
    fromWGS84     = fld.Str(allow_none=True)


def _select_transforms(db, id=None):
    return db.execute(f'''
        select
            id,
            control_links as "controlLinks"
        from coordinate_transform
        {id and 'where id=%(id)s' or ''}
    ''', (id,))


@api.route('/coordinate_transform', methods=['GET'])
def get_all_transforms():
    with db2.pool.connection() as con:
        cur = _select_transforms(con)
        return jsonify(cur.fetchall())


@api.route('/coordinate_transform', methods=['PUT'])
def replace_all_transforms():
    data = CoordinateTransformSchema(many=True).load(request.get_json())
    recs = []

    with db2.pool.connection() as con:
        con.execute('delete from coordinate_transform')
        if len(data):
            recs = execute_values(con, '''
                insert into coordinate_transform
                    (id, control_links)
                values %s
                returning
                    id,
                    control_links as "controlLinks"
            ''', data, template='''(
                %(id)s,
                %(controlLinks)s
            )''', fetch=True)
    return jsonify(recs)


@api.route('/coordinate_transform', methods=['DELETE'])
def delete_all_transforms(id):
    with db2.pool.connection() as con:
        con.execute('delete from coordinate_transform')
    return '', 204


@api.route('/match/<int:id>', methods=['GET'])
def match_devices(id):
    with db2.pool.connection() as con:
        cur = con.execute('''
            select distinct(device.id)
            from
                device,
                feature left join shape on find_shape(%s)=shape.id
            where
                    st_srid(device.center) = 4326
                and st_contains(
                        shape.geometries,
                        uncertainty_circle(device.center, device.radius))
        ''', (id,))
        return jsonify([v['id'] for v in cur.fetchall()])


@api.route('/sql', methods=['POST'])
def sql_api():
    query = request.get_json()
    with db2.pool.connection() as con:
        cur = con.execute(query)
        return jsonify(cur.fetchall())


@api.route("/bbox", methods=['GET'])
def get_bbox():
    '''
    Return the minimal bounding box that fits all the features of the user,
    simply the min/max lon/lat values for the user's features alternative
    implementation would be to not explicitly store and maintain max/min lat/lon
    and extract from polygon (performance tradeoff)
    '''
    with db2.pool.connection() as con:
        cur = con.execute('''
        select min(minLon), min(minLat), max(maxLon), max(maxLat)
        from feature
        ''')
        return jsonify(cur.fetchall())


@api.route("/contains", methods=['GET'])
def contains():
    '''
    Return the feature that contains the point. If there are multiple features
    that contain the point, e.g., a neighborhood, building, and a room, return
    them all matching features and sort them from the smallest to the largest by
    size/area.
    '''
    args = request.args
    if not args or "lng" not in args or "lat" not in args:
        abort(400, description='malformed request, both lng and lat are required')

    try:
        lng = float(args['lng'])
        lat = float(args['lat'])
    except Exception as e:
        abort(400, description='invalid value for lng/lat')

    with db2.pool.connection() as con:
        # ST_GeomFromEWKT converts input lon/lat into postgres geometry point
        # 'geojson_polygon' refers to the 'geojson_polygon' column, where the polygon features are stored, '::geometry' suffix is needed for postgis to interpret serialized data as a geometry
        # ST_Within(point,polygon)='t' returns True if point is within the polygon, False otherwise
        # ORDER BY ST_Area(geojson_polygon::geometry) ASC orders matching features by the area of their polygons in ascending order (smallest to largest)

        # converts lon, lat to EWKT format for ST_GeomFromEWKT
        # OGC Extended Well-Known text, https://postgis.net/docs/ST_GeomFromEWKT.html
        cur = con.execute('''
        select * from feature
        where ST_Within(ST_GeomFromEWKT(%s),
            geojson_polygon::geometry)='t'
        order by ST_Area(geojson_polygon::geometry) ASC
        ''', ('SRID=4326;POINT(%f %f)' % (lng, lat)))
        return jsonify(cur.fetchall())


#
# =======================================================================
#

@api.route("/OSM", methods=['POST'])
def load_OSM():
    '''
    Load buildings (ways) within the given bounding box from OSM, with metadata
    from google places
    '''
    count = 0
    start_time = time.time()
    data = request.get_json()
    if type(data) != dict:
        abort(400, description='Invalid or missing JSON object in request body')

    # boolean that specifies whether existing entries should be updated or skipped
    update = data.get('update', None)
    if update not in ("True", "False"):
        abort(400, description='Please spedify whether existing entries should be updated (True/False)')
    update = True if update == "True" else False

    # default bounds is around the campus
    bounding_box = data.get('bounds', [40.805606, -73.966620, 40.811191, -73.958443])
    if type(bounding_box) != list:
        abort(400, description='Missing or invalid bounding box: format: [min Longitude, min Latitude, max Longitude, max Latitude] default: [40.805606, -73.966620, 40.811191, -73.958443]') 

    try:
        bounding_box = validate_bounds(bounding_box)
    except Exception as e:
        abort(400, description='Invalid bounding box: %s' % str(e))

    db_name, db_user, db_host, db_password, db_sslmode = [item.split('=')[1] for item in os.getenv('DB').split()]
    GC_API_KEY = os.getenv('GC_API_KEY')

    engine = connect(db_name, db_user, db_host, db_password, db_sslmode)

    ensure_feature_table(engine)

    # get OSM response within the bounding box (excluding relations)
    osm_response = requests.post(
            'https://overpass-api.de/api/interpreter',
            data = f'data=%5Bout%3Ajson%5D%3B%0Away({req_bounds[0]}%2C+{req_bounds[1]}%2C+{req_bounds[2]}%2C+{req_bounds[3]})%5B%22building%22%5D%3B%0A(._%3B%3E%3B)%3B%0Aout+body%3B'
        )

    # convert osm response to geojson format
    GEOJson = osm2geojson.json2geojson(json.loads(osm_response.text))
    print('###### CONVERTED GEOJSON ######')
    # print(geojson[:200],'\n......')

    nodes, ways = {}, {}

    for elem in GEOJson['features']:
        print('\n\n',elem)
        querystr = None
        wayCoords = elem['geometry']['coordinates'][0]

        # extract lists of lon and lat from coordinates. example:
        # >>> list(zip(*[(1,2),(3,4)]))
        # [(1, 3), (2, 4)]
        wayLons, wayLats = zip(*wayCoords)

        # min/max lon and lat are used to find a bounding box for the feature and get an approximate center coordinate
        minLat, maxLat, minLon, maxLon = min(wayLats), max(wayLats), min(wayLons), max(wayLons)
        # approximate center coordinate used for reverse geo-lookup if no name/address available
        avgLat, avgLon = (minLat+maxLat)/2, (minLon+maxLon)/2
        # google places API takes bound of (minLat, minLon, maxLat, maxLon) format for bias (prioritize results within/around the bound)
        # this bias is used for disambiguation in case of names like 'visitor center'
        bounds = 'rectangle:%3.7f,%3.7f|%3.7f,%3.7f' %(minLat, minLon, maxLat, maxLon)

        # first try using address, then name, then alt_name, if none of the above exist, use reverse-geocoding
        if 'tags' in elem['properties']:
            tags = elem['properties']['tags']
            if "addr:housenumber" in tags and "addr:street" in tags and "addr:postcode" in tags:
                querystr = "%s %s %s" % (tags['addr:housenumber'], tags['addr:street'], tags['addr:postcode'])
            elif "name" in tags:
                querystr = "%s" % (tags['name'])
            elif "alt_name" in tags:
                querystr = "%s" % (tags['alt_name'])

            if "name" in tags:
                name = tags['name']
            elif "alt_name" in tags:
                name = tags['alt_name']
            else:
                name = None

        # using id from OSM converted GeoJSON
        # replacing forward slash in uuid to prevent issue with url paths
        feature_id = str(elem['properties']['id']).replace('/','_')
        # for determing total bound for all of a user's features
        obj_bounds = '|'.join([str(minLon), str(minLat), str(maxLon), str(maxLat)])
        # 'now' is a special string that tells postgres to use current time as timestamp
        last_modified = 'now'
        # all of the features fetched here from OSM are buildings, specified in the request used for fetching osm_response
        feature_type = 'building'

        # find the placeid(s) used for google places API to fetch metadata
        placeid = None
        if querystr:
            search_response = requests.get(
            'https://maps.googleapis.com/maps/api/place/findplacefromtext/json?',
            params={
                'input': querystr,
                'inputtype': 'textquery',
                'fields':'name,place_id,formatted_address,geometry',
                'locationbias':bounds,
                'key': GC_API_KEY
            })
            print(search_response.text)
            search_response = json.loads(search_response.text)
            if search_response and search_response['candidates']:
                placeid = [candidate['place_id'] for candidate in search_response['candidates']]
                print(placeid)
        else:
            geocode_response = requests.get(
            'https://maps.googleapis.com/maps/api/geocode/json?',
            params={
                'latlng': '%3.8f,%3.8f' % (avgLat, avgLon),
                'key': GC_API_KEY,
            })
            print('###NAME/ADDRESS NOT FOUND, USING GEO_CODE SEARCH###\n',geocode_response.text[:200], "\n......")
            geocode_response = json.loads(geocode_response.text)
            if geocode_response and geocode_response['results']:
                placeid = [result['place_id'] for result in geocode_response['results']]
                print(placeid)

        # if multiple placeids are found for the location, details of each one is fetched and placed in a list
        detail_responses = []
        if placeid:
            for query_id in placeid:
                resp = requests.get(
                    'https://maps.googleapis.com/maps/api/place/details/json?',
                    params={
                        'place_id': query_id,
                        'key': GC_API_KEY,
                    })
                detail_responses.append(json.loads(resp.text))
                # prevent bursts of high-concurrency requests to Google Places
                time.sleep(0.2)
            print('\n### number of google_places matches: ', len(detail_responses))
            print(detail_responses[:200], "\n......")

        # if no name found in OSM, have one exact google places match, use name from google places
        if len(detail_responses)==1 and not name:
            if 'name' in detail_responses[0]['result'] and detail_responses[0]['result']['name']:
                name = detail_responses[0]['result']['name']

        # if no readable name available, set it as 'unnamed feature'
        if not name:
            name = 'Unnamed feature'

        # if update is True, refresh data for existing entries using UPDATE keyword in postgres, EXCLUDED.x keyword extract args for INSERT rows that would be otherwise excluded due to duplicate feature_id
        if update:
            command = """
                INSERT INTO feature (feature_id, name, feature_type, geojson, googleplaces_info, last_modified, minLon, minLat, maxLon, maxLat, geojson_polygon)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,ST_GeomFromGeoJSON(%s))
                ON CONFLICT (feature_id)
                DO UPDATE SET
                    name = EXCLUDED.name,
                    feature_type = EXCLUDED.feature_type,
                    geojson = EXCLUDED.geojson,
                    googleplaces_info = EXCLUDED.googleplaces_info,
                    last_modified = EXCLUDED.last_modified,
                    minLon = EXCLUDED.minLon,
                    minLat = EXCLUDED.minLat,
                    maxLon = EXCLUDED.maxLon,
                    maxLat = EXCLUDED.maxLat,
                    geojson_polygon = EXCLUDED.geojson_polygon
                """
        # otherwise, do simple insert, leave existing entries unmodified
        else:
            command = """
                INSERT INTO feature (feature_id, name, feature_type, geojson, googleplaces_info, last_modified, minLon, minLat, maxLon, maxLat, geojson_polygon)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,ST_GeomFromGeoJSON(%s))
                """
        count += 1

        # arguments for prepared SQL statment
        args = (feature_id, name, feature_type, json.dumps(elem), json.dumps(detail_responses), last_modified, minLon, minLat, maxLon, maxLat, json.dumps(elem['geometry']))

        try:
            cur = engine.cursor()
            cur.execute(command, args)
            cur.close()
            engine.commit()

        except (Exception, psycopg2.DatabaseError) as error:
            print(error)
            engine.close()
            raise(error)

    if engine is not None:
        engine.close()

    timetook = time.time()-start_time
    return 'loaded %d buildings from OSM within bounding box %f %f %f %f, took %f seconds' %(count, req_bounds[0], req_bounds[1], req_bounds[2], req_bounds[3], timetook)


@api.route("/feature/<uuid>", methods=['PUT'])
def update_feature(uuid):
    '''
    Used to update an *existing* feature with the JSON data from the request body
    '''
    data = request.get_json()
    if type(data) != dict:
        abort(400, description='Invalid or missing JSON object in request body')

    # check input format
    for k in data:
        if k not in ('name', 'feature_type', 'geojson', 'googleplaces_info', 'minLon', 'minLat', 'maxLon', 'maxLat', 'geojson_polygon', 'merge', 'is_ST_Polygon'):
            abort(400, description='key %s not in schema or cannot be modified' %k)
        if k in ('minLon', 'minLat', 'maxLon', 'maxLat') and not data[k].isnumeric():
            abort(400, description='value %s for field %s has incorrect type, expected float/double/decimal' %(data[k], k))
        if k in ('name', 'feature_type', 'geojson', 'googleplaces_info', 'geojson_polygon') and type(data[k]) != str:
            abort(400, description='value %s for field %s has incorrect type, expected str' %(data[k], k))
        if k == 'last_modified':
            abort(400, description='last_modified should not be set manually')

    if 'geojson_polygon' in data and 'is_ST_Polygon' not in data:
        abort(400, description='missing parameter: is_ST_Polygon:True/False, please specify whether input polygon is ST_Polygon or GeoJSON format, True:ST_Polygon, False:GeoJSON Ploygon')

    # optional argument to merge new update fields with existing fields, if not merging, will null fields not specified in update
    merge = True if 'merge' in data and data['merge']=="True" else False

    # argument specifying that the input for 'geojson_polygon' column is of ST_Polygon format
    is_ST_Polygon = True if 'is_ST_Polygon' in data and data["is_ST_Polygon"]=="True" else False

    engine = connect()
    cur = engine.cursor()

    # fetch existing record
    cur.execute("SELECT * FROM feature WHERE feature_id=%s", (uuid,))
    records = cur.fetchall()
    if not records: abort(400, description='feature with uuid %s does not exist, use /feature/<uuid> POST to create it' %uuid)

    if merge:
        # create dict mapping between col name and existing row values
        zipped = zip(('feature_id', 'owner_uid', 'name', 'feature_type', 'geojson', 'googleplaces_info', 'last_modified', 'minLon', 'minLat', 'maxLon', 'maxLat', 'geojson_polygon'), records[0])
        rowdict = {k:v for k,v in zipped}
        # update the dict for this entry with new data
        for k in data:
            if k in rowdict: rowdict[k]=data[k]
        row = list(rowdict.values())

    else:
        # not merging
        # 'feature_id', 'owner_uid' would not be modified, other fields will be set to null unless specified in this update by user
        row = [records[0][0], records[0][1]]
        for k in ('name', 'feature_type', 'geojson', 'googleplaces_info', 'last_modified', 'minLon', 'minLat', 'maxLon', 'maxLat', 'geojson_polygon'):
            if k in data:
                row.append(data[k])
            else:
                row.append(None)

    # 'last_modified' timestamp column for an update should always have value set as 'now'
    row[6] = 'now'
    if not row[2]: row[2] = 'Unnamed feature'

    # if given JSON serialized geoJSON feature, convert to ST_Polygon
    if not is_ST_Polygon:
        cur.execute("SELECT ST_GeomFromGeoJSON(%s)", (row[-1],))
        row[-1] = cur.fetchall()[0]

    # if missing, extract min/max Lon/Lat values from polygon via postgis query if polygon is supplied
    if row[-1] and any((row[-2]==None, row[-3]==None, row[-4]==None, row[-5]==None)):
        command = "SELECT ST_XMin(%s::geometry), ST_YMin(%s::geometry), ST_XMax(%s::geometry), ST_YMax(%s::geometry)"
        cur.execute(command, [row[-1]]*4)
        row[-5],row[-4],row[-3],row[-2] = cur.fetchall()[0]

    command = """
        INSERT INTO feature (feature_id, owner_uid, name, feature_type, geojson, googleplaces_info, last_modified, minLon, minLat, maxLon, maxLat, geojson_polygon)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (feature_id)
        DO UPDATE SET
            owner_uid = EXCLUDED.owner_uid,
            name = EXCLUDED.name,
            feature_type = EXCLUDED.feature_type,
            geojson = EXCLUDED.geojson,
            googleplaces_info = EXCLUDED.googleplaces_info,
            last_modified = EXCLUDED.last_modified,
            minLon = EXCLUDED.minLon,
            minLat = EXCLUDED.minLat,
            maxLon = EXCLUDED.maxLon,
            maxLat = EXCLUDED.maxLat,
            geojson_polygon = EXCLUDED.geojson_polygon
        """
    try:
        cur = engine.cursor()
        cur.execute(command, row)
        cur.close()
        engine.commit()
        engine.close()
    except (Exception, psycopg2.DatabaseError) as error:
        engine.close()
        raise(error)

    return 'successfully updated feature with uuid %s, \nnew values: %s' %(uuid, jsonify([r if len(str(r))<20 else r[:20]+'......' for r in row]))


@api.route("/feature", methods=['POST'])
def create_feature():
    '''
    Create a new feature (the database will assign the uuid if none is provided). The feature must not exist.
    '''
    data = request.get_json()
    if type(data) != dict:
        abort(400, description='Invalid or missing JSON feature in request body')

    # check input format
    for k in ('feature_type', 'geojson_polygon', 'is_ST_Polygon'):
        if k not in data:
            abort(400, description='required field %s is missing' %k)

    # generate random alphanumerical feature_id if not provided, chance of collision should be negligible and acceptable for non-production code
    feature_id = ''.join(random.choice('1234567890abcdefghijklmnopqrstuvwxyz') for i in range(20)) if 'feature_id' not in data else data['feature_id']
    last_modified = 'now'
    name = 'Unnamed feature' if 'name' not in data else data['name']
    feature_type = data['feature_type']
    geojson_polygon = data['geojson_polygon']
    geojson = None if 'geojson' not in data else data['geojson']
    googleplaces_info = None if 'googleplaces_info' not in data else data['googleplaces_info']
    # argument specifying that the input geojson_polygon is of ST_Polygon format
    is_ST_Polygon = True if 'is_ST_Polygon' in data and data["is_ST_Polygon"]=="True" else False
    minLon = None if 'minLon' not in data else data['minLon']
    minLat = None if 'minLat' not in data else data['minLat']
    maxLon = None if 'maxLon' not in data else data['maxLon']
    maxLat = None if 'maxLat' not in data else data['maxLat']

    engine = connect()
    cur = engine.cursor()

    # check if record exists
    cur.execute("SELECT * FROM feature WHERE feature_id=%s", (feature_id,))
    records = cur.fetchall()
    if records: abort(400, description='feature with uuid %s already exists, use /feature/<uuid> PUT to modify it' %feature_id)

    # if given JSON serialized geoJSON object, convert to ST_Polygon
    if not is_ST_Polygon:
        cur.execute("SELECT ST_GeomFromGeoJSON(%s)", (geojson_polygon,))
        geojson_polygon = cur.fetchall()[0]

    # if missing, extract min/max Lon/Lat values from polygon
    if geojson_polygon and any((minLon==None, minLat==None, maxLon==None, maxLat==None)):
        command = "SELECT ST_XMin(%s::geometry), ST_YMin(%s::geometry), ST_XMax(%s::geometry), ST_YMax(%s::geometry)"
        cur.execute(command, [geojson_polygon]*4)
        minLon,minLat,maxLon,maxLat = cur.fetchall()[0]

    command = """
        INSERT INTO feature (feature_id, name, feature_type, geojson, googleplaces_info, last_modified, minLon, minLat, maxLon, maxLat, geojson_polygon)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """
    args = (feature_id, name, feature_type, geojson, googleplaces_info, last_modified, minLon, minLat, maxLon, maxLat, geojson_polygon)

    try:
        cur = engine.cursor()
        cur.execute(command, args)
        cur.close()
        engine.commit()
        engine.close()
    except (Exception, psycopg2.DatabaseError) as error:
        engine.close()
        raise(error)

    return 'created feature with uuid %s' % feature_id


dir = os.path.dirname(__file__)
frontend_dir = f'{dir}/ui/public'

@app.route('/')
@app.route('/<path:path>')
def serve_frontend(path='index.html'):
    return send_from_directory(frontend_dir, path)