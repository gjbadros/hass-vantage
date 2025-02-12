"""
Support for Vantage lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.vantage/
"""
import logging
import asyncio
from functools import cached_property

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_TRANSITION,
    ATTR_HS_COLOR,
    LIGHT_TURN_ON_SCHEMA,
    LightEntity,
    LightEntityFeature,
    ColorMode
)

from homeassistant.util.color import (
    color_hs_to_RGB,
    color_temperature_to_rgb,
    color_RGB_to_hs,
    color_temperature_mired_to_kelvin,
    color_temperature_kelvin_to_mired,
)

from homeassistant.helpers import entity_platform
from homeassistant.helpers.service import async_extract_entity_ids

from ..vantage import VantageDevice, VANTAGE_DEVICES, VANTAGE_CONTROLLER

_LOGGER = logging.getLogger(__name__)

VANTAGE_SET_STATE_SCHEMA = LIGHT_TURN_ON_SCHEMA
SERVICE_VANTAGE_SET_STATE = "set_state"

DEPENDENCIES = ["vantage"]


# pylint: disable=unused-argument
async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Vantage lights."""

    devs = []

    async def async_handle_set_state(call):
        entity_ids = await async_extract_entity_ids(hass, call, True)
        if entity_ids:
            entities = [entity for entity in devs if entity.entity_id in entity_ids]
#            tasks = []
            for light in entities:
                await light.set_state(**call.data)
#                task = light.set_state(**call.data)
#                tasks.append(hass.async_create_task(task))
#            if tasks:
#                await asyncio.wait(tasks)

    for (area_name, device) in hass.data[VANTAGE_DEVICES]["light"]:
        dev = VantageLight(area_name, device, hass.data[VANTAGE_CONTROLLER])
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
    return float((level * 100) / 255)


def to_hass_level(level):
    """Convert the given Vantage (0.0-100.0) light level to HASS (0-255)."""
    return int((level * 255) / 100)


class VantageLight(VantageDevice, LightEntity):
    """Representation of a Vantage Light, including dimmable."""

    def __init__(self, area_name, vantage_device, controller):
        """Initialize the light."""
        self._prev_brightness = None
        VantageDevice.__init__(self, area_name, vantage_device, controller)

    @cached_property
    def supported_features(self):
        """Flag supported features."""
        return (
            LightEntityFeature.TRANSITION
            # | SUPPORT_BRIGHTNESS
            # | (SUPPORT_COLOR_TEMP if self._vantage_device.support_color_temp else 0)
            # | (SUPPORT_COLOR if self._vantage_device.support_color else 0)
        )
    
    @cached_property
    def supported_color_modes(self) -> set[ColorMode] | set[str] | None:
        """Flag supported color modes."""
        temp_set = {ColorMode.BRIGHTNESS}
        if self._vantage_device.support_color_temp:
            temp_set.add(ColorMode.COLOR_TEMP)
        if self._vantage_device.support_color:
            temp_set.add(ColorMode.SUPPORT_COLOR)
        return temp_set

    @property
    def color_mode(self) -> ColorMode | None:
        """Return the color mode."""
        if self._vantage_device.support_color and self._vantage_device.rgb and self._vantage_device.rgb != [0,0,0]:
            return ColorMode.SUPPORT_COLOR
        if self._vantage_device.support_color_temp and self._vantage_device.color_temp and self._vantage_device.color_temp != 2700:
            return ColorMode.COLOR_TEMP
        return ColorMode.BRIGHTNESS


    @property
    def brightness(self):
        """Return the brightness of the light."""
        new_brightness = to_hass_level(self._vantage_device.last_level())
        if new_brightness != 0:
            self._prev_brightness = new_brightness
        return new_brightness

    @property
    def color_temp(self):
        """Return the color temperature of the light."""
        ct = self._vantage_device._color_temp
        return color_temperature_kelvin_to_mired(ct)

    @property
    def rgb_color(self):
        """Return the RGB color value."""
        return self._vantage_device.rgb

    def color_temperature_to_dw_27k41k(self, kelvin):
        """Convert a kelvin color temperature to a pair of values
        for a dual-white LED fixture with a 27K white and a 41K white
        light source."""
        if kelvin < 2700:
            red = 255
            blue = 0
        elif kelvin > 4100:
            red = 0
            blue = 255
        else:
            frac = (kelvin - 2700) / (4100 - 2700)
            blue = frac * 255
            red = 255 - blue
        # max_color = max(red, blue)
        # ratio = 255 / max_color * self.brightness / 255
        answer = (red, 0, blue)
        _LOGGER.debug("using %s for color temp %s", answer, kelvin)
        return answer

    @property
    def hs_color(self):
        """Return the HS color value."""
        #  rgb = self._vantage_device.rgb
        # hs = color_RGB_to_hs(*rgb)
        # return hs  # self._vantage_device.hs
        return self._vantage_device.hs

    def _set_level(self, brightness):
        """Set the level, including other dirty properties."""
        self._vantage_device.level = to_vantage_level(brightness)

    async def async_turn_on(self, **kwargs):
        if ATTR_BRIGHTNESS in kwargs and self._vantage_device.is_dimmable:
            brightness = kwargs[ATTR_BRIGHTNESS]
        elif self._prev_brightness == 0:
            brightness = 255
        else:
            brightness = self._prev_brightness
        self._prev_brightness = brightness
        kwargs[ATTR_BRIGHTNESS] = brightness
        self.hass.async_create_task(self.set_state(**kwargs))

    def _set_ramp(self, **kwargs):
        transition_time_in_s = kwargs.get(ATTR_TRANSITION, 1)
        self._vantage_device.set_ramp_sec(transition_time_in_s,
                                          transition_time_in_s,
                                          transition_time_in_s)

    async def set_state(self, **kwargs):
        """Turn the light on."""
        _LOGGER.debug("light.set_state(%s) to %s",
                      self._vantage_device, kwargs)
        self._set_ramp(**kwargs)
        if ATTR_BRIGHTNESS in kwargs:
            # TODO: is_dimmable test fails for GROUP load types
            # and self._vantage_device.is_dimmable:
            
            brightness = kwargs[ATTR_BRIGHTNESS]
            self._set_level(brightness)
        if ATTR_RGB_COLOR in kwargs:
            _LOGGER.debug("%s set via ATTR_RGB_COLOR", self)
            self._vantage_device.rgb = kwargs[ATTR_RGB_COLOR]
        elif ATTR_HS_COLOR in kwargs:
            _LOGGER.debug("%s set via ATTR_HS_COLOR", self)
            hs_color = kwargs[ATTR_HS_COLOR]
            # rgb = color_hs_to_RGB(*hs_color)
            # self._vantage_device.rgb = [*rgb]
            self._vantage_device.hs = hs_color
        elif ATTR_COLOR_TEMP in kwargs or ATTR_KELVIN in kwargs:
            if ATTR_KELVIN in kwargs:
                _LOGGER.debug(
                    "%s set via ATTR_KELVIN - %s", self, kwargs[ATTR_KELVIN]
                )
                kelvin = kwargs[ATTR_KELVIN]
            else:
                _LOGGER.debug(
                    "%s set via ATTR_COLOR_TEMP - %s", self, kwargs[ATTR_COLOR_TEMP]
                )
                # Color temp in HA is in mireds:
                # https://en.wikipedia.org/wiki/Mired
                # M = 1000000/KELVIN_TEMP
                kelvin = int(color_temperature_mired_to_kelvin(kwargs[ATTR_COLOR_TEMP]))
            _LOGGER.debug("%s vantage color temp kelvin = %s", self, kelvin)
            if self._vantage_device._dmx_color:
                # do conversion
                rgb = color_temperature_to_rgb(kelvin)
                self._vantage_device.rgb = [*rgb]
            elif self._vantage_device._load_type == "DW":
                rgb = self.color_temperature_to_dw_27k41k(kelvin)
                self._vantage_device.rgb = [*rgb]
            self._vantage_device.color_temp = kelvin

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        self._set_ramp(**kwargs)
        self._vantage_device.level = 0
        self.async_write_ha_state()

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._vantage_device.last_level() > 0

    async def async_update(self):
        """Call when forcing a refresh of the device."""
        if self._prev_brightness is None:
            self._prev_brightness = to_hass_level(self._vantage_device.level)
