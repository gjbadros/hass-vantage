"""
Support for Vantage variables and other sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.vantage/
"""

import logging

# we want to restore entity values because vantage models dry-contacts
# and keypads and buttons as instantaneous actions whose state
# cannot be queried from the vantage controller, so we need
# to use hass state to keep track of them between reboots
from homeassistant.helpers.restore_state import RestoreEntity

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
        if device.needs_poll():
            dev = VantagePollingSensor(area_name, device,
                                       hass.data[VANTAGE_CONTROLLER])
        else:
            dev = VantageSensor(area_name, device,
                                hass.data[VANTAGE_CONTROLLER])
        devs.append(dev)

    add_devices(devs, True)
    return True


class VantageSensor(VantageDevice, RestoreEntity):
    """Representation of a Sensor."""

    def __init__(self, area_name, vantage_device, controller):
        """Initialize the sensor."""
        VantageDevice.__init__(self, area_name, vantage_device, controller)
        self._unit_of_measurement = None
        self._device_class = None
        k = self._vantage_device.kind
        if k == 'temperature':
            self._unit_of_measurement = '°C'
            self._device_class = 'temperature'
        if k == 'power':
            self._unit_of_measurement = 'watt'
            self._device_class = 'power'
        if k == 'current':
            self._unit_of_measurement = 'amp'
            self._device_class = 'power'
        if k == 'light':
            self._unit_of_measurement = 'lm'
            self._device_class = 'illuminance'
        _LOGGER.debug("Created sensor (%s): %s", vantage_device.kind,
                      vantage_device.name)

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if not state:
            _LOGGER.warning("no state retrieved for %s", self)
            return
        _LOGGER.info("got state for %s = %s", self, state.state)
        self._vantage_device.value = state.state
        self.hass.async_add_job(self._update_callback)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._vantage_device.value

    def update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement for this sensor."""
        return self._unit_of_measurement

    @property
    def device_class(self):
        """Return the device class for this sensor."""
        return self._device_class

    def _update_callback(self, _device):
        """Run when invoked by pyvantage when the device state changes."""
        self.schedule_update_ha_state()


# TODO: this maybe could be just returning true for should_poll
class VantagePollingSensor(VantageSensor):
    """Representation of a Vantage sensor that needs polling."""
    def update(self):
        """Fetch new data."""
        self._vantage_device.update()

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._vantage_device.value

    @property
    def should_poll(self):
        """These devices do poll."""
        return True
