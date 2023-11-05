#!/bin/bash

if [ -n "$AUTHORITATIVE" ] ; then
    lost-server shape get $AUTHORITATIVE >/dev/null 2>&1 || {
        echo "Authoritative shape not found in the local database"
        lost-server osm fetch $AUTHORITATIVE
    }
fi

exec lost-server start $@