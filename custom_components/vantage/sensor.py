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

from homeassistant.components.sensor import SensorDeviceClass

from ..vantage import VantageDevice, VANTAGE_DEVICES, VANTAGE_CONTROLLER, button_pressed

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ["vantage"]


async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup the sensor platform."""
    devs = []
    for (area_name, device) in hass.data[VANTAGE_DEVICES]["sensor"]:
        if not area_name:
            area_name = ""
        if device.needs_poll():
            dev = VantagePollingSensor(area_name, device, hass.data[VANTAGE_CONTROLLER])
        else:
            dev = VantageSensor(area_name, device, hass.data[VANTAGE_CONTROLLER])
        devs.append(dev)

    async_add_devices(devs, True)
    return True


class VantageSensor(VantageDevice, RestoreEntity):
    """Representation of a Sensor."""

    def __init__(self, area_name, vantage_device, controller):
        """Initialize the sensor."""
        VantageDevice.__init__(self, area_name, vantage_device, controller)
        self._unit_of_measurement = None
        self._device_class = None
        k = self._vantage_device.kind
        if k == "temperature":
            self._unit_of_measurement = "°C"
            self._device_class = "temperature"
        if k == "power":
            self._unit_of_measurement = "watt"
            self._device_class = "power"
        if k == "current":
            self._unit_of_measurement = "amp"
            self._device_class = "power"
        if k == "lightsensor":
            self._unit_of_measurement = "lm"
            self._device_class = SensorDeviceClass.ILLUMINANCE
        _LOGGER.debug(
            "Created sensor (%s): %s", vantage_device.kind, vantage_device.name
        )

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if not state:
            _LOGGER.warning("no state retrieved for %s", self)
            return
        _LOGGER.debug("got state for %s = %s", self, state.state)
        self._vantage_device.set_initial_value(state.state)

    @property
    def assumed_state(self) -> bool:
        """Return true if unable to access real state of entity."""
        return True

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._vantage_device.value

    async def async_update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """

    def _update_callback(self, device):
        """Run when invoked by pyvantage when the device state changes."""
        self.schedule_update_ha_state()

        if self._vantage_device.kind == "button":
            button_pressed(self.hass, device)


# TODO: this maybe could be just returning true for should_poll
class VantagePollingSensor(VantageSensor):
    """Representation of a Vantage sensor that needs polling."""

    async def async_update(self):
        """Fetch new data."""
        self._vantage_device.update()

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._vantage_device.value

    @property
    def assumed_state(self) -> bool:
        """Return true if unable to access real state of entity."""
        return False

    @property
    def should_poll(self):
        """These devices do poll."""
        return True
