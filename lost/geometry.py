from collections import namedtuple

# The order of coordinate axes across various standards is as follows:
# GeoJSON:            [lon, lat]
# PostGIS (WKT, WKB): [lon, lat]
# KML:                [lon, lat]
# EPSG:4326           [lat, lon]
# GML:                [lat, lon]
Point = namedtuple('Point', ['lon', 'lat'])
