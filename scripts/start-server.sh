#!/bin/bash

if [ -n "$SERVICE_AREA" ] ; then
    lost-server shape get $SERVICE_AREA >/dev/null 2>&1 || {
        echo "Service area shape not found in the local database"
        lost-server osm fetch $SERVICE_AREA
    }
fi

exec lost-server start $@