#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging

def _isItTrue(val):
    if isinstance(val, str):
        return val.lower() == 'true'
    return bool(val)

# Class Params
class Params:
    def __init__(self):
        # Grdf params
        self.grdfUsername = os.getenv('GRDF_USERNAME', '')
        self.grdfPassword = os.getenv('GRDF_PASSWORD', '')
        self.grdfStartDate = os.getenv('GRDF_STARTDATE', '2020-01-01')
        
        # Mqtt params
        self.mqttHost = os.getenv('MQTT_HOST', '')
        self.mqttPort = int(os.getenv('MQTT_PORT', '1883'))
        self.mqttClientId = os.getenv('MQTT_CLIENTID', 'gazpar2mqtt')
        self.mqttUsername = os.getenv('MQTT_USERNAME', '')
        self.mqttPassword = os.getenv('MQTT_PASSWORD', '')
        self.mqttQos = int(os.getenv('MQTT_QOS', '1'))
        self.mqttTopic = os.getenv('MQTT_TOPIC', 'gazpar')
        self.mqttRetain = _isItTrue(os.getenv('MQTT_RETAIN', 'true'))
        self.mqttSsl = _isItTrue(os.getenv('MQTT_SSL', 'false'))
        
        # Run params
        self.scheduleTime = os.getenv('SCHEDULE_TIME')
        
        # Publication params
        self.standalone = _isItTrue(os.getenv('STANDALONE_MODE', 'false'))
        self.hassDiscovery = _isItTrue(os.getenv('HASS_DISCOVERY', 'false'))
        self.hassPrefix = os.getenv('HASS_PREFIX', 'homeassistant')
        self.hassDeviceName = os.getenv('HASS_DEVICE_NAME', 'gazpar')
        
        # Publication in HA long term statistics 
        self.hassLts = _isItTrue(os.getenv('HASS_LTS', 'false'))
        self.hassLtsDelete = _isItTrue(os.getenv('HASS_LTS_DELETE', 'false'))
        self.hassToken = os.getenv('HASS_LTS_TOKEN', '')
        self.hassStatisticsUri = os.getenv('HASS_LTS_URI', '/api/services/recorder/import_statistics')
        self.hassHost = os.getenv('HASS_LTS_HOST', '')
        
        self.hassSsl = _isItTrue(os.getenv('HASS_SSL', 'false'))
        self.hassSslGateway = _isItTrue(os.getenv('HASS_SSL_GATEWAY', 'true'))
        self.hassSslCertfile = os.getenv('HASS_SSL_CERTFILE', '')
        self.hassSslKeyfile = os.getenv('HASS_SSL_KEYFILE', '')
        
        # Database params
        self.dbInit = _isItTrue(os.getenv('DB_INIT', 'false'))
        self.dbPath = os.getenv('DB_PATH', '/data')
        
        # Debug param
        self.debug = _isItTrue(os.getenv('DEBUG', 'false'))
        
        # Threshold param
        self.thresholdPercentage = int(os.getenv('THRESHOLD_PERCENTAGE', '80'))
        
        # Influx db
        self.influxEnable = _isItTrue(os.getenv('INFLUXDB_ENABLE', 'false'))
        self.influxHost = os.getenv('INFLUXDB_HOST', '')
        self.influxPort = int(os.getenv('INFLUXDB_PORT', '8086'))
        self.influxBucket = os.getenv('INFLUXDB_BUCKET', '')
        self.influxOrg = os.getenv('INFLUXDB_ORG', '')
        self.influxToken = os.getenv('INFLUXDB_TOKEN', '')
        self.influxHorizon = os.getenv('INFLUXDB_HORIZON', '')

        # Price params
        self.priceKwhDefault = float(os.getenv('PRICE_KWH_DEFAULT', '0.07'))
        self.priceFixDefault = float(os.getenv('PRICE_FIX_DEFAULT', '0.9'))
        self.pricePath = os.getenv('PRICE_PATH', '/data')

    def checkParams(self):
        """Validate required parameters."""
        if not self.grdfUsername:
            logging.error("Parameter GRDF username is mandatory.")
            return False
        elif not self.grdfPassword:
            logging.error("Parameter GRDF password is mandatory.")
            return False
        elif not self.mqttHost:
            logging.error("Parameter MQTT host is mandatory.")
            return False
        else:
            if not self.standalone and not self.hassDiscovery:
                logging.warning("Both Standalone mode and Home assistant discovery are disabled. No value will be published to MQTT! Please check your parameters.")
            return True

    def logParams(self):
        """Display parameters in log."""
        logging.info("Configuration Summary:")
        logging.info("  MQTT: %s:%s (SSL: %s)", self.mqttHost, self.mqttPort, self.mqttSsl)
        logging.info("  Mode: Standalone=%s, HA Discovery=%s", self.standalone, self.hassDiscovery)
        
        if self.hassDiscovery:
            logging.info("  Home Assistant: %s (LTS: %s)", self.hassHost, self.hassLts)
        
        if self.influxEnable:
            logging.info("  InfluxDB: %s:%s (%s)", self.influxHost, self.influxPort, self.influxBucket)
        
        if self.scheduleTime:
            logging.info("  Schedule: Daily at %s", self.scheduleTime)
        
        if self.debug:
            logging.debug("  Debug mode enabled")
            logging.debug("  Database path: %s", self.dbPath)
            logging.debug("  Price settings: kWh=%s, Fix=%s", self.priceKwhDefault, self.priceFixDefault)

# Create a default instance if imported directly
if __name__ == '__main__':
    params = Params()
