![GitHub release (with filter)](https://img.shields.io/github/v/release/vingerha/gazpar_2_mqtt)

## Introduction / status

Reworked from the great repo by yukulehe/gazpar2mqtt (who also provided a large part of the docu), now that GRDF is again without Captcha.
Main differences are in the login method, now using virtual browser (old method still does not work), and allowing to export to HA Long Term Statistics
- It is working as a container (tested by 3 people) on collecting data in SQLite, MQTT, InfluxDb, Home Assistant sensor and HA energy-dashboard
- It is working as an add on (tested by myself and 1 other person)
- no verification if the now 2+-year old code from yukulehe/gazpar2mqtt is still valid **in its entirety**, bits and pieces may not work perfectly anylonger
- Not yet tested
  - Grafana dashboard template
  - Cost calculation from prices file

For usage and installation etc. see [DOCUMENTATION](https://github.com/vingerha/gazpar_2_mqtt/wiki)

## Changelogs :
- 0.6.0
  - Fix issue with double naming in the HA sensor
  - Fix issue with incorrect device_classes for the sensors
  - Fix issue with restarting due to non-copied hass_ws.py
- 0.5.0
  - Use webservice for loading data to Home Assistant, previously this was a spook (app) api
  - collect published measures (periodically values registered by GRDF)
- 0.4.1
  - initial fix to load also published (non-daily) data, may need a rebuild of the db
  - reduce non-needed stuff for the addon
- 0.4.0
  - introduce addon (initial version)
  - Documentation in French (thanks @Cazzoo)  
- 0.3.0 (container only)
  - enable Influx also from docker-compose parameters
  - set log directory one step higher to avoid adding logs into /app
... history removed
  
## Roadmap :

- Home assistant custom entity card (low prio)

### Thanks
The vast majority of the work was done by @yukulehe ... to which masisve thanks goes out !
