#!/bin/sh
set -e

if [ ! -z "$GAZPAR_2_MQTT_APP" ]; then
    APP="$GAZPAR_2_MQTT_APP"
else
    APP="/app"
fi

echo "Using '$APP' as APP directory"

if [ ! -f "$APP/database.py" ]; then
    echo "database.py non existing, copying default to app..."
    cp /app_temp/database.py "$APP/database.py"
fi
if [ ! -f "$APP/gazpar.py" ]; then
    echo "gazpar.py non existing, copying default to app..."
    cp /app_temp/gazpar.py "$APP/gazpar.py"
fi
if [ ! -f "$APP/gazpar2mqtt.py" ]; then
    echo "gazpar2mqtt.py non existing, copying default to app..."
    cp /app_temp/gazpar2mqtt.py "$APP/gazpar2mqtt.py"
fi
if [ ! -f "$APP/hass.py" ]; then
    echo "hass.py non existing, copying default to app..."
    cp /app_temp/hass.py "$APP/hass.py"
fi
if [ ! -f "$APP/influxdb.py" ]; then
    echo "$APP/influxdb.py non existing, copying default to app..."
    cp /app_temp/influxdb.py "$APP/influxdb.py"
fi
if [ ! -f "$APP/mqtt.py" ]; then
    echo "mqtt.py non existing, copying default to app..."
    cp /app_temp/mqtt.py "$APP/mqtt.py"
fi
if [ ! -f "$APP/param.py" ]; then
    echo "param.py non existing, copying default to app..."
    cp /app_temp/param.py "$APP/param.py"
fi
if [ ! -f "$APP/price.py" ]; then
    echo "price.py non existing, copying default to app..."
    cp /app_temp/price.py "$APP/price.py"
fi
if [ ! -f "$APP/standalone.py" ]; then
    echo "$APP/standalone non existing, copying default to app..."
    cp /app_temp/standalone.py "$APP/standalone.py"
fi

exec "$@"