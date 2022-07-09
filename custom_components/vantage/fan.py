import logging

from homeassistant.components.fan import (
    FanEntity,
    ATTR_PERCENTAGE,
    SUPPORT_SET_SPEED
)
from ..vantage import VantageDevice, VANTAGE_DEVICES, VANTAGE_CONTROLLER

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ["vantage"]

async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Vantage lights."""

    devs = []

    for (area_name, device) in hass.data[VANTAGE_DEVICES]["fan"]:
        dev = VantageFan(area_name, device, hass.data[VANTAGE_CONTROLLER])
        devs.append(dev)

    async_add_devices(devs, True)
    platform = entity_platform.current_platform.get()
    platform.async_register_entity_service(
        SERVICE_VANTAGE_SET_STATE,
        VANTAGE_SET_STATE_SCHEMA, "set_state"
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
        self._set_level(kwargs[ATTR_PERCENTAGE])
        await self.async_set_percentage(kwargs[ATTR_PERCENTAGE])
        #await self.async_update_ha_state()
    
    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        self._vantage_device.level = 0
        await self.async_update_ha_state()

    def _set_level(self, brightness):
        """Set the level, including other dirty properties."""
        self._vantage_device.level = to_vantage_level(brightness)        

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._vantage_device.last_level() > 0

    async def async_update(self):
        """Call when forcing a refresh of the device."""
        if self._prev_speed is None:
            self._prev_speed = to_hass_level(self._vantage_device.level)
