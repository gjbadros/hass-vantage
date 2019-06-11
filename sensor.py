"""
Support for Vantage variables as sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.vantage/
"""

import logging

from homeassistant.helpers.entity import Entity

from ..vantage import (
    VantageDevice, VANTAGE_DEVICES, VANTAGE_CONTROLLER)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['vantage']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""
    devs = []
    for (area_name, device) in hass.data[VANTAGE_DEVICES]['sensor']:
        if not area_name:
            area_name = ""
        dev = VantageSensor(area_name, device, hass.data[VANTAGE_CONTROLLER])
        devs.append(dev)

    add_devices(devs, True)
    return True


class VantageSensor(VantageDevice, Entity):
    """Representation of a Sensor."""

    def __init__(self, area_name, vantage_device, controller):
        """Initialize the sensor."""
        VantageDevice.__init__(self, area_name, vantage_device, controller)
        _LOGGER.info("Created sensor (%s): %s", vantage_device.type,
                     vantage_device.name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._vantage_device.value

    def update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """

    def _update_callback(self, _device):
        """Run when invoked by pyvantage when the device state changes."""
        self.schedule_update_ha_state()

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attr = super().device_state_attributes
        return {**attr, **self._vantage_device._extra_info}
