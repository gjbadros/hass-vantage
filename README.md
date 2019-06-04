hass-vantage
============

By Greg J. Badros <badros@gmail.com>

For license information, see LICENSE -- use at your own risk.


This is a custom component for the Vantage Infusion whole-home lighting
system for use with Home Assistant.

It relies on my pyvantage module (from PyPi or github).

Put these files in .homeassistant/custom_components/vantage

And configure using a config like:

```
vantage:
  host: 192.168.0.123
  disable_cache: True
  username: !secret vantage_username
  password: !secret vantage_password
  exclude_areas: "SPARE RELAYS"
```

and then restart home assistant.
