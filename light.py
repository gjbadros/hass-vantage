"""
Support for Vantage lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.vantage/
"""
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_RGB_COLOR, ATTR_HS_COLOR,
    SUPPORT_BRIGHTNESS, SUPPORT_COLOR, SUPPORT_COLOR_TEMP, Light)

from homeassistant.util.color import (
    color_hs_to_RGB, color_temperature_to_rgb, color_RGB_to_hs,
    color_temperature_mired_to_kelvin,
    color_temperature_kelvin_to_mired)

from ..vantage import (
    VantageDevice, VANTAGE_DEVICES, VANTAGE_CONTROLLER)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['vantage']


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Vantage lights."""
    devs = []
    for (area_name, device) in hass.data[VANTAGE_DEVICES]['light']:
        dev = VantageLight(area_name, device, hass.data[VANTAGE_CONTROLLER])
        devs.append(dev)

    add_devices(devs, True)
    return True


def to_vantage_level(level):
    """Convert the given HASS light level (0-255) to Vantage (0.0-100.0)."""
    return float((level * 100) / 255)


def to_hass_level(level):
    """Convert the given Vantage (0.0-100.0) light level to HASS (0-255)."""
    return int((level * 255) / 100)


class VantageLight(VantageDevice, Light):
    """Representation of a Vantage Light, including dimmable."""

    def __init__(self, area_name, vantage_device, controller):
        """Initialize the light."""
        self._prev_brightness = None
        VantageDevice.__init__(self, area_name, vantage_device, controller)
        vantage_device.set_ramp_sec(1, 1, 1)

    @property
    def supported_features(self):
        """Flag supported features."""
        return (SUPPORT_BRIGHTNESS |
                (SUPPORT_COLOR_TEMP if self._vantage_device.support_color_temp else 0) |
                (SUPPORT_COLOR if self._vantage_device.support_color else 0))

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
            frac = (kelvin-2700) / (4100-2700)
            blue = frac*255
            red = 255 - blue
        max_color = max(red, blue)
        ratio = 255/max_color * self.brightness/255
        answer = (red*ratio, 0, blue*ratio)
        _LOGGER.debug("using %s for color temp %s", answer, kelvin)
        return (red*ratio, 0, blue*ratio)

    @property
    def hs_color(self):
        """Return the HS color value."""
        rgb = self._vantage_device.rgb
        hs = color_RGB_to_hs(*rgb)
        return hs # self._vantage_device.hs

    def turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs and self._vantage_device.is_dimmable:
            brightness = kwargs[ATTR_BRIGHTNESS]
        elif self._prev_brightness == 0:
            brightness = 255
        else:
            brightness = self._prev_brightness
        self._prev_brightness = brightness
        self._vantage_device.level = to_vantage_level(brightness)
        if ATTR_RGB_COLOR in kwargs:
            _LOGGER.debug("set via ATTR_RGB_COLOR")
            self._vantage_device.rgb = kwargs[ATTR_RGB_COLOR]
        elif ATTR_HS_COLOR in kwargs:
            _LOGGER.debug("set via ATTR_HS_COLOR")
            hs_color = kwargs[ATTR_HS_COLOR]
            rgb = color_hs_to_RGB(*hs_color)
            self._vantage_device.rgb = [*rgb]
        elif ATTR_COLOR_TEMP in kwargs:
            _LOGGER.debug("set via ATTR_COLOR_TEMP - %s", kwargs[ATTR_COLOR_TEMP])
            # Color temp in HA is in mireds: https://en.wikipedia.org/wiki/Mired
            # M = 1000000/KELVIN_TEMP
            kelvin = int(color_temperature_mired_to_kelvin(
                kwargs[ATTR_COLOR_TEMP]))
            _LOGGER.debug("vantage color temp kelvin = %s", kelvin)
            if self._vantage_device._dmx_color:
                # do conversion
                rgb = color_temperature_to_rgb(kelvin)
                self._vantage_device.rgb = [*rgb]
            elif self._vantage_device._load_type == "DW":
                rgb = self.color_temperature_to_dw_27k41k(kelvin)
                self._vantage_device.rgb = [*rgb]
            self._vantage_device.color_temp = kelvin
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the light off."""
        self._vantage_device.level = 0
        self.schedule_update_ha_state()

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._vantage_device.last_level() > 0

    def update(self):
        """Call when forcing a refresh of the device."""
        if self._prev_brightness is None:
            self._prev_brightness = to_hass_level(self._vantage_device.level)
