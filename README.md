# IMPORTANT NOTE: development ongoing

Reworked from the great repo by yukulehe/gazpar2mqtt, now that GRDF is again without Captcha.
Main differences are in the login method, now using virtual browser (old method still does not work), and allowing to export to HA Long Term Statistics

### Important: 
- working to collect data in SQLite and MQTT but under development, various functions may disappear or be modified.
- no verification if the now 2-year old code from yukulehe/gazpar2mqtt is still valid **in its entirety**
- only tested via docker image and docker-compose, see [INSTALLATION](https://github.com/vingerha/gazpar_2_mqtt?tab=readme-ov-file#installation-and-usage)
- This repo does not support add-ons for HAOS, a request is outstanding with [@AlexBelgium](https://github.com/alexbelgium/alexbelgium/commits?author=alexbelgium) to consider this repo as part of his library....
- Contains functionality from yukulehe/gazpar2mqtt which is not yet tested
  - Grafana dashboard template
  - Cost calculation from prices file

For installation etc. see [DOCUMENTATION])(https://github.com/vingerha/gazpar_2_mqtt/wiki)

## Changelogs :
- 0.2.0 :
  - add export to HA Long Term Statistic
- 0.1.0 :
  - Basis from yukulehe/gazpar2mqtt
  - add login via selenium
  
## Roadmap :

- Home assistant custom entity card (low prio)
- Home assistan load of monthly GRDG figures as long term statistics

### Thanks
The vast majority of the work was done by @yukulehe ...for which thanks goes out !
