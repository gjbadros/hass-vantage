import logging

from homeassistant.components.fan import (
    FanEntity,
    FanEntityFeature,
    ATTR_PERCENTAGE,
    SUPPORT_SET_SPEED,
    SERVICE_TURN_ON,
    SERVICE_SET_PERCENTAGE
)

import voluptuous as vol

from homeassistant.helpers import entity_platform
from homeassistant.helpers.service import async_extract_entity_ids

from ..vantage import VantageDevice, VANTAGE_DEVICES, VANTAGE_CONTROLLER

_LOGGER = logging.getLogger(__name__)

VANTAGE_SET_STATE_SCHEMA = SERVICE_TURN_ON
SERVICE_VANTAGE_SET_STATE = "set_state"

DEPENDENCIES = ["vantage"]

async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):

    devs = []

    for (area_name, device) in hass.data[VANTAGE_DEVICES]["fan"]:
        dev = VantageFan(area_name, device, hass.data[VANTAGE_CONTROLLER])
        devs.append(dev)

    async_add_devices(devs, True)
    platform = entity_platform.current_platform.get()
    platform.async_register_entity_service(
        SERVICE_TURN_ON,
        {
            vol.Optional(ATTR_PERCENTAGE): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            )
        },
        "async_turn_on",
    )
    platform.async_register_entity_service(
        SERVICE_SET_PERCENTAGE,
        {
            vol.Required(ATTR_PERCENTAGE): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            )
        },
        "async_set_percentage",
        [FanEntityFeature.SET_SPEED],
    )
    return True

def to_vantage_level(level):
    """Convert the given HASS light level (0-255) to Vantage (0.0-100.0)."""
    return float(level)


def to_hass_level(level):
    """Convert the given Vantage (0.0-100.0) light level to HASS (0-255)."""
    return int(level)

class VantageFan(VantageDevice, FanEntity):

    def __init__(self, area_name, vantage_device, controller):
        self._prev_speed = None
        VantageDevice.__init__(self, area_name, vantage_device, controller)
    
        
    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_SET_SPEED
    
    async def async_turn_on(self, **kwargs):
        if ATTR_PERCENTAGE in kwargs:
            speed_percent = kwargs[ATTR_PERCENTAGE]
        elif self._prev_speed == 0:
            speed_percent = 100
        else:
            speed_percent = self._prev_speed
        self._prev_speed = speed_percent
        kwargs[ATTR_PERCENTAGE] = speed_percent
        self.hass.async_create_task(self.set_state(**kwargs))
    
    async def set_state(self, **kwargs):
        _LOGGER.debug("fan.set_state(%s) to %s",
                      self._vantage_device, kwargs)
        self.set_percentage(kwargs[ATTR_PERCENTAGE])
        await self.async_set_percentage(kwargs[ATTR_PERCENTAGE])
        #await self.async_update_ha_state()
    
    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        self._vantage_device.level = 0
        await self.async_update_ha_state()       

    def set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        self._vantage_device.level = to_vantage_level(percentage)

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._vantage_device.last_level() > 0

    async def async_update(self):
        """Call when forcing a refresh of the device."""
        if self._prev_speed is None:
            self._prev_speed = to_hass_level(self._vantage_device.level)
