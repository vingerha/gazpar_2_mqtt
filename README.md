## Introduction / status
Fork of vingerha/gazpar2mqtt. Main differences are in the login method and allowing to export to HA Long Term Statistics
- Can be installed as an addon (not tested) and container; collecting data in SQLite, MQTT, InfluxDb, Home Assistant sensor and HA energy-dashboard (LTS)
- Fixes (including schedule update) and Docker security improvements.
- no 100% verification if the now 2+-year old source from yukulehe/gazpar2mqtt is still valid **in its entirety**, bits and pieces may not work perfectly anylonger
- Not yet tested: Grafana dashboard template

For usage and installation etc. see [DOCUMENTATION](https://github.com/vingerha/gazpar_2_mqtt/wiki/Home-fr-FR)

## Changelogs :
- 0.8.7
  - Align Long Term Statistics with HA Core
  - As a result: loss of option to use Apexcharts for LTS, awaiting feature request
  - Removed dummy sensors
- 0.8.6
  - Add gross gas daily consumption as sensors, providing more detail
  - Change default value for LTS dummy to 0 (was 1)
  - Improve on price calculation
- 0.8.5
  - Add gross gas daily consumption as sensors, providing more detail
  - Change default value for LTS dummy sensors to 0 (was 1)
  - Improve on price calculation
- 0.8.5
  Removal of chromium for login, replaced by request.session
- 0.8.0
  Extending LTS sensors with kWh and price import:
  - sensor.[device]_[pce-alias]_consumption_stat : for daily figures in m3
  - sensor.[device]_[pce-alias]_consumption_kwh_stat : for daily figures in kWh
  - sensor.[device]_[pce-alias]_consumption_cost_stat : daily cost
  - sensor.[device]_[pce-alias]_consumption_pub_stat : for periodic figures in m3
  - sensor.[device]_[pce-alias]_consumption_kwh_pub_stat : for periodic figures in kWh
  - sensor.[device]_[pce-alias]_consumption_cost_pub_stat : periodic cost
- 0.7.0 
  The LTS sensor name can no longer be chosen and is fixed to 
  - sensor.[device]_[pce-alias]_consumption_stat : for daily figures
  - sensor.[device]_[pce-alias]_consumption_pub_stat : for periodically 'published' figures 
  Reason: previously the LTS sensors were added without a regular sensor, this makes their use impossible for e.g. apexcharts who uses the regular sensor-name also for statistics.
  These 2 sensors will appear both in HA as in HA statistics
- 0.6.5
  - Allow to select a date from which to collect data from GRDF (max 3y back in time)
  - Allow import of published measures into Long Term Statistics
  - Allow to delete Long Term Ststaistics for all PCE
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
... history removed
  
## Roadmap :

- Home assistant custom entity card (low prio)

### Thanks
The vast majority of the work was done by @yukulehe ... to whom massive thanks goes out !
