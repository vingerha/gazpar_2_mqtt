#!/usr/bin/env bashio
# shellcheck shell=bash
set -e
####################
# LOAD CONFIG.YAML #
####################

# Exit if /config is not mounted
if [ ! -d /config ]; then
	echo "Error: /config not mounted"
    exit 0
fi

# Default location
CONFIGTEMPLATE="/templates/config.yaml"
CONFIGSOURCE="/config/gazpar_2_mqtt/config.yaml"
CONFIGUSERDIR="/homeassistant/gazpar_2_mqtt"
CONFIGUSER="/homeassistant/gazpar_2_mqtt/config.yaml"

mkdir -p /config/gazpar_2_mqtt


if [ ! -f "$CONFIGUSER" ]; then
    echo "... no config basis file found. Copying template to $CONFIGUSER, please adapt this and restart"
	mkdir -p "$CONFIGUSERDIR"
	cp -rf "$CONFIGTEMPLATE" "$CONFIGUSER"
	exit 1
fi

cp -rf "$CONFIGUSER" "$CONFIGSOURCE"

# Export all yaml entries as env variables

while IFS= read -r line; do
    # Clean output
    line="${line//[\"\']/}"
    # Check if secret
    if [[ "${line}" == *'!secret '* ]]; then
        echo "secret detected"
        secret=${line#*secret }
        # Check if single match
        secretnum=$(sed -n "/$secret:/=" /config/secrets.yaml)
        [[ $(echo $secretnum) == *' '* ]] && bashio::exit.nok "There are multiple matches for your password name. Please check your secrets.yaml file"
        # Get text
        secret=$(sed -n "/$secret:/p" /config/secrets.yaml)
        secret=${secret#*: }
        line="${line%%=*}='$secret'"
    fi
    # Data validation
    if [[ "$line" =~ ^.+[=].+$ ]]; then
        # extract keys and values
        KEYS="${line%%=*}"
        VALUE="${line#*=}"
        line="${KEYS}=${VALUE}"
        export "$line"
        # export to python
        if command -v "python3" &>/dev/null; then
            [ ! -f /env.py ] && echo "import os" > /env.py
            echo "os.environ['${KEYS}'] = '${VALUE//[\"\']/}'" >> /env.py
            python3 /env.py
        fi
        # set .env
        if [ -f /.env ]; then echo "$line" >> /.env; fi
        mkdir -p /etc
        echo "$line" >> /etc/environment
        # Export to scripts
        if cat /etc/services.d/*/*run* &>/dev/null; then sed -i "1a export $line" /etc/services.d/*/*run* 2>/dev/null; fi
        if cat /etc/cont-init.d/*run* &>/dev/null; then sed -i "1a export $line" /etc/cont-init.d/*run* 2>/dev/null; fi
        # For s6
        if [ -d /var/run/s6/container_environment ]; then printf "%s" "${VALUE}" > /var/run/s6/container_environment/"${KEYS}"; fi
        echo "export $line" >> ~/.bashrc
        # Show in log
    else
        echo "$line does not follow the correct structure. Please check your yaml file."
    fi
done <"$CONFIGSOURCE"

########################
# LOAD CONFIG.YAML END #
########################

#####################
# Autodiscover mqtt #
#####################

if bashio::config.true 'mqtt_autodiscover'; then
    bashio::log.info "mqtt_autodiscover is defined in options, attempting autodiscovery..."
    # Check if available
    if ! bashio::services.available "mqtt"; then bashio::exit.nok "No internal MQTT service found. Please install Mosquitto broker"; fi
    # Get variables
    bashio::log.info "... MQTT service found, fetching server detail (you can enter those manually in your config file) ..."
    MQTT_HOST=$(bashio::services mqtt "host")
    export MQTT_HOST
    MQTT_PORT=$(bashio::services mqtt "port")
    export MQTT_PORT
    MQTT_SSL=$(bashio::services mqtt "ssl")
    export MQTT_SSL
    MQTT_USERNAME=$(bashio::services mqtt "username")
    export MQTT_USERNAME
    MQTT_PASSWORD=$(bashio::services mqtt "password")
    export MQTT_PASSWORD

    # Export variables
    for variables in "MQTT_HOST=$MQTT_HOST" "MQTT_PORT=$MQTT_PORT" "MQTT_SSL=$MQTT_SSL" "MQTT_USERNAME=$MQTT_USERNAME" "MQTT_PASSWORD=$MQTT_PASSWORD"; do
        sed -i "1a export $variables" /etc/services.d/*/*run* 2>/dev/null || true
        # Log
        bashio::log.blue "$variables"
    done
fi
#####################
# Autodiscover mqtt end #
####################

APP="/app"

exec "$@"