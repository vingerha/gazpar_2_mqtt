# NOT WORKING NOT WORKING ... in process of being reviewed

Home assistant add-on: gazpar_2_mqtt


## About

Python script to fetch GRDF data and publish data to a mqtt broker.
See its github for all informations : https://github.com/vingerha/gazpar_2_mqtt

## Configuration

Options can be configured through two ways :

- Addon options

```yaml
CONFIG_LOCATION: /config/gazpar2mqtt/config.yaml # Sets the location of the config.yaml (see below)
mqtt_autodiscover: true # Shows in the log the detail of the mqtt local server (if available). It can then be added to the config.yaml file.
TZ: Europe/Paris # Sets a specific timezone
```

- Config.yaml

Configuration is done by customizing the config.yaml that can be found in /config/gazpar_2_mqtt/config.yaml

The complete list of options can be seen here : https://github.com/vingerha/gazpar_2_mqtt

## Installation

The installation of this add-on is pretty straightforward and not different in
comparison to installing any other Hass.io add-on.

1. [Add my Hass.io add-ons repository][repository] to your Hass.io instance.
1. Install this add-on.
1. Click the `Save` button to store your configuration.
1. Start the add-on.
1. Check the logs of the add-on to see if everything went well.
1. Carefully configure the add-on to your preferences, see the official documentation for for that.

