hass-vantage
============

By Greg J. Badros <badros@gmail.com>

For license information, see LICENSE -- use at your own risk.


This is a custom component for the Vantage Infusion whole-home lighting
system for use with Home Assistant.

It relies on my pyvantage module (from PyPi at https://pypi.org/project/pyvantage/
or github at https://github.com/gjbadros/pyvantage).

Put these files in .homeassistant/custom_components/vantage

And add something like the following to configuration.yaml:

```
vantage:
  host: 192.168.0.123
  disable_cache: True
  username: !secret vantage_username
  password: !secret vantage_password
  exclude_areas: "SPARE RELAYS"
```

And add the following to secrets.yaml:

vantage_username: [my_username]
vantage_password: [my_password]

and then restart home assistant.

Note: if your Vantage system is not set up with a username and password you can
elide the username: and password: lines in the configuration.yaml file, and skip
setting up secrets.yaml.  Or, just add a password to your Vantage!
