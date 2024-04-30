# IMPORTANT NOTE: development ongoing
## Request: anyone interested in providing/helping a translation of the documentation into French ?

Reworked from the great repo by yukulehe/gazpar2mqtt (also large part of the docu), now that GRDF is again without Captcha.
Main differences are in the login method, now using virtual browser (old method still does not work), and allowing to export to HA Long Term Statistics

### Important: 
- This **repo does not support add-ons** for HAOS, a request is outstanding with [@AlexBelgium](https://github.com/alexbelgium/alexbelgium/commits?author=alexbelgium) to consider this repo as part of his library....
- It is working (tested by 3 people) on collecting data in SQLite and MQTT and displayed in Home Assistant
- no verification if the now 2+-year old code from yukulehe/gazpar2mqtt is still valid **in its entirety**, bits and pieces may not work perfectly anylonger
- only tested via docker image and docker-compose
- Not yet tested
  - Grafana dashboard template
  - Cost calculation from prices file
For installation etc. see [DOCUMENTATION](https://github.com/vingerha/gazpar_2_mqtt/wiki)

## Changelogs :
- 0.3.0
  - enable Influx also from docker-compose parameters
  - set log directory one step higher to avoid adding logs into /app
- 0.2.0 :
  - add export to HA Long Term Statistic
- 0.1.0 :
  - Basis from yukulehe/gazpar2mqtt
  - add login via selenium
  
## Roadmap :

- Home assistant custom entity card (low prio)
- Home assistan load of monthly GRDG figures as long term statistics

### Thanks
The vast majority of the work was done by @yukulehe ... to which masisve thanks goes out !
