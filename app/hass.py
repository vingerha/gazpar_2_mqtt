#!/usr/bin/env python3
### Define Home Assistant-related functionality. ###
# More info on HA discovery : https://www.home-assistant.io/docs/mqtt/discovery

import json
import logging

# Constants
SENSOR = "sensor"
BINARY = "binary_sensor"

# Hass device class
GAS_TYPE = "gas"
ENERGY_TYPE = "energy"
CONNECTIVITY_TYPE = "connectivity"
PROBLEM_TYPE = "problem"
COST_TYPE = "monetary"
NONE_TYPE = None

# Hass state_class
ST_MEAS = 'measurement'
ST_TT = 'total'
ST_TTI = 'total_increasing'

# Hass Others
MANUFACTURER = "GRDF"



# Class Home assistant
class Hass:
    
    # Constructor
    def __init__(self,prefix):
        
        self.prefix = prefix # discovery prefix
        self.deviceList = []
        
    def addDevice(self,device):
        self.deviceList.append(device)
        return device
              

# Class Home assistant Device
class Device:
    
    # Constructor
    def __init__(self,hass,pceId,deviceId, deviceName):
        
        self.hass = hass
        self.id = deviceId
        self.name = deviceName
        
        self.entityList = []
        
        self.configPayload = {
            "identifiers": [self.id],
            "name": self.name,
            "model": pceId,
            "manufacturer": MANUFACTURER
            }
        
        # Add device to hass
        hass.addDevice(self)
        
        
    # Add entity
    def addEntity(self,entity):
        self.entityList.append(entity)
    
    # Return the state payload of all entities of the device
    def getStatePayload(self):
        
        # Init payload
        payload = {}
        
        # Append value to list in the corresponding state topic
        for myEntity in self.entityList:
            payload[myEntity.configTopic] = myEntity.getConfigPayloadJson()
            if myEntity.value is not None:
                payload[myEntity.stateTopic]  = myEntity.value
            if myEntity.attributes:
                payload[myEntity.attributesTopic] = myEntity.attributes
        
        # Return json formatted
        return payload
    
    
# Class Home assistant Entity
class Entity:
    
    # Constructor
    def __init__(self,device,type,id,name,deviceClass=None,stateClass=None,unit=None):
        
        logging.debug("Initialise hass device id %s",id)
        logging.debug("Initialise hass device self.id %s",id)
        
        
        # Variables
        self.device = device
        self.type = type
        self.id = id
        self.name = name
        self.deviceClass = deviceClass
        self.stateClass = stateClass
        self.unit = unit
        self.statePayload = None
        self.value = None
        self.attributes = {}
        
        logging.debug("Initialise hass device self.device.id %s",self.device.id)
        
        # Set topics
        self.configTopic = f"{self.device.hass.prefix}/{type}/{self.device.id}/{self.id}/config"
        self.stateTopic = f"{self.device.hass.prefix}/{type}/{self.device.id}/{self.id}/state"
        self.attributesTopic = f"{self.device.hass.prefix}/{type}/{self.device.id}/{self.id}/attributes"

        
        # Set config payload
        self.configPayload = {}
        if self.deviceClass is not None:
            self.configPayload["device_class"] = self.deviceClass
        if self.stateClass is not None:
            self.configPayload["state_class"] = self.stateClass
        if self.unit is not None:
            self.configPayload["unit_of_measurement"] = self.unit
        self.configPayload["name"] = f"{self.name}"
        self.configPayload["unique_id"] = f"{self.device.id}_{self.id}"
        self.configPayload["state_topic"] = self.stateTopic
        self.configPayload["json_attributes_topic"] = f"{self.attributesTopic}"
        self.configPayload["device"] = self.device.configPayload

        # Add entity to device
        self.device.addEntity(self)
        
    
    # Return config payload in Json format
    def getConfigPayloadJson(self):
        return json.dumps(self.configPayload)
    
    # Set state value
    def setValue(self,value):
        self.value = value
        
    # Add attributes
    def addAttribute(self,key,value):
        self.attributes[key] = value

    # Add attributes
    def addAttributej(self,value):
        self.attributes = value
        
    # Get attributes payload
    def getAttribute(self):
        return json.dumps(self.attributes)
        

