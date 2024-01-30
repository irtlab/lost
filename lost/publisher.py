import click
from .osm import query_overpass, extract_boundary
import json
import osm2geojson
from . import db
from psycopg.types.json import Jsonb
from .guid import GUID
from psycopg_pool import ConnectionPool
import sys

class LoSTPublisher:
    def __init__(self, server_id, db: ConnectionPool, table):
        self.server_id = server_id
        self.db = db
        self.table = table
        self.shape_ids = []

    #This function only updates the shape table
    def update_db(self, geometry, attrs):
        with self.db.connection() as con:
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
                self.shape_ids.append(shape_id)
            else:
                shape_id = previous.id


            return shape_id


    #Delete entries in shape table after publisher stops running
    def delete_shapes(self):
        with self.db.connection() as con:
            for shape_id in self.shape_ids:
                con.execute('''
                    DELETE FROM shape WHERE id = %s
                ''', (shape_id,))
        self.shape_ids = []
        click.echo("Removed geometries from shape table.")


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
    except db.Error as e:
        print(f"Error while connecting to datababase '{db_url}': {e}")
        sys.exit(1)

@cli.command(help='<Longitude> <Latitude> <Longitude> <Latitude>. Top left coordinate and bottom right coordinate')
@click.argument('top_left_lon')
@click.argument('top_left_lat')
@click.argument('bottom_right_lon')
@click.argument('bottom_right_lat')
def publish(top_left_lon, top_left_lat, bottom_right_lon, bottom_right_lat):  
    lost_publisher = LoSTPublisher("lost-server", db.pool, "shape")

    # Query to fetch building data from OpenStreetMap
    query = f"""(way[building]({bottom_right_lat}, {top_left_lon}, {top_left_lat}, {bottom_right_lon});)"""
    data = query_overpass(query, 25)

    # Convert OSM data to GeoJSON
    geojson_data = osm2geojson.json2geojson(data)

    # Processing each feature in the GeoJSON data
    if 'features' in geojson_data:
        for feature in geojson_data['features']:
            # Create a FeatureCollection for each feature
            feature_collection = {
                "type": "FeatureCollection",
                "features": [feature]
            }
            # Extract boundary and attributes
            geometry, attrs = extract_boundary(feature_collection)
            
            # Insert polygons into the shape table
            try:
                shape_id = lost_publisher.update_db(geometry, attrs)
                click.echo(f'Loaded feature with shape ID: {shape_id}')
            except Exception as e:
                click.echo(f'Error loading feature: {e}')

    try:
        while True:
            pass
    except KeyboardInterrupt:
        # Exit and delete geometry with Ctrl-C pressed.
        lost_publisher.delete_shapes()

if __name__ == '__main__':
    cli()
