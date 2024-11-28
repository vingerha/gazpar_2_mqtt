#!/bin/sh
set -e

# Change UID/GID at runtime if needed
if [ ! -z "${PUID}" ] && [ ! -z "${PGID}" ]; then
    echo "Updating UID:GID to ${PUID}:${PGID}..."
    groupmod -o -g "${PGID}" appuser
    usermod -o -u "${PUID}" appuser
    chown -R appuser:appuser /app /data
fi

# Ensure data directory exists and has correct permissions
if [ ! -d "/data" ]; then
    echo "Creating /data directory..."
    mkdir -p /data
    chown -R appuser:appuser /data
fi

echo "Starting Gazpar2MQTT..."
# Switch to appuser before executing the main process
exec su -s /bin/sh -c "exec $*" appuser