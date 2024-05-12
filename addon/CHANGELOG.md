## 0.8.0 (12-05-2024)
Extending LTS sensors with kWh and price
sensor.[device]_[pce-alias]_consumption_stat : for daily figures in m3
sensor.[device]_[pce-alias]_consumption_kwh_stat : for daily figures in kWh
sensor.[device]_[pce-alias]_consumption_cost_stat : daily cost
sensor.[device]_[pce-alias]_consumption_pub_stat : for periodic figures in m3
sensor.[device]_[pce-alias]_consumption_kwh_pub_stat : for periodic figures in kWh
sensor.[device]_[pce-alias]_consumption_cost_pub_stat : periodic cost

## 0.7.0 (10-05-2024)
The LTS sensor name can no longer be chosen and is fixed to :

sensor.[device]_[pce-alias]_consumption_stat : for daily figures
sensor.[device]_[pce-alias]_consumption_stat_pub : for periodically 'published' figures 

## 0.6.5 (09-05-2024)

Allow import of published measures into Long Term Statistics
Allow to delete Long Term Ststaistics for all PCE
  
## 0.6.0 (08-05-2024)

Fix issue with double naming in the HA sensor
Fix issue with incorrect device_classes for the sensors
Fix issue with restarting due to non-copied hass_ws.py

## 0.5.0 (03/04-05-2024) - addon + container

Add webservice as main process to push Long Term Stats
Fix issues, e.g standalone mode

## 0.4.0 (03/04-05-2024) - addon + container

introduce addon, small modifications to the core code



