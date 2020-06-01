"""
Support for Vantage switches/relays.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.vantage/
"""
import logging

from homeassistant.components.switch import SwitchDevice
from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
)
from ..vantage import VantageDevice, VANTAGE_DEVICES, VANTAGE_CONTROLLER
from ..vantage.sensor import VantagePollingSensor

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ["vantage"]


# pylint: disable=unused-argument
async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Set up the Vantage lights."""
    devs = []
    controller = hass.data[VANTAGE_CONTROLLER]
    for (area_name, device) in hass.data[VANTAGE_DEVICES]["switch"]:
        if device.kind == 'variable_bool':
            dev = VantageVariableSwitch(area_name, device, controller)
        else:
            dev = VantageSwitch(area_name, device, controller)
        devs.append(dev)

    async_add_devices(devs, True)
    return True


def to_vantage_level(level):
    """Convert the given HASS level (0-255) to Vantage (0.0-100.0)."""
    return float((level * 100) / 255)


def to_hass_level(level):
    """Convert the given Vantage (0.0-100.0) level to HASS (0-255)."""
    return int((level * 255) / 100)


class VantageVariableSwitch(VantagePollingSensor, SwitchDevice):
    """Represents a boolean variable sensor as a switch."""

    def __init__(self, area_name, vantage_device, controller):
        """Initialize the sensor."""
        _LOGGER.debug("SwitchSensor = %s", vantage_device)
        VantagePollingSensor.__init__(self,
                                      area_name, vantage_device, controller)

    # this gets overridden by VantagePollingSensor and we want to get
    # back to the ToggleEntity behavior since this is a switch
    @property
    def state(self) -> str:
        """Return the state."""
        return STATE_ON if self.is_on else STATE_OFF

    def turn_on(self, **kwargs):
        self._vantage_device.value = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        self._vantage_device.value = False
        self.schedule_update_ha_state()

    @property
    def is_on(self):
        """Return true iff variable is True."""
        return self._vantage_device.value


class VantageSwitch(VantageDevice, SwitchDevice):
    """Representation of a Vantage Switch (not dimmable)."""

    def __init__(self, area_name, vantage_device, controller):
        """Initialize the light."""
        self._prev_brightness = None
        VantageDevice.__init__(self, area_name, vantage_device, controller)

    def turn_on(self, **kwargs):
        """Turn the light on."""
        if self._prev_brightness == 0:
            brightness = 255
        else:
            brightness = self._prev_brightness
        self._prev_brightness = brightness
        self._vantage_device.level = to_vantage_level(brightness)
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the light off."""
        self._vantage_device.level = 0
        self.schedule_update_ha_state()

    @property
    def is_on(self):
        """Return true iff device is on."""
        return self._vantage_device.last_level() > 0

    async def async_update(self):
        """Call when forcing a refresh of the device."""
        if self._prev_brightness is None:
            self._prev_brightness = to_hass_level(self._vantage_device.level)
