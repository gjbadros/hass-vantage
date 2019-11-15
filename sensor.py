"""
Support for Vantage variables and other sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.vantage/
"""

import logging
import time
import collections
import threading

# we want to restore entity values because vantage models dry-contacts
# and keypads and buttons as instantaneous actions whose state
# cannot be queried from the vantage controller, so we need
# to use hass state to keep track of them between reboots
from homeassistant.helpers.restore_state import RestoreEntity

from ..vantage import VantageDevice, VANTAGE_DEVICES, VANTAGE_CONTROLLER

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
        if k == "light":
            self._unit_of_measurement = "lm"
            self._device_class = "illuminance"
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
        _LOGGER.info("got state for %s = %s", self, state.state)
        self._vantage_device.set_initial_value(state.state)
        if self._vantage_device.kind == "button":
            self._clicktracker = ButtonClickTracker(
                self.hass, self._vantage_device, self._controller,
                self.entity_id.replace("sensor.", "", 1))

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
        if self._vantage_device.kind == "button":
            if self.state == "PRESS":
                self._clicktracker.pressed()
            elif self.state == "RELEASE":
                self._clicktracker.released()
            else:
                _LOGGER.warning("Unexpected state for button %s: %s",
                                self, self.state)



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

class ButtonClickTracker:
    """Generates events for single click, double tap, etc. on buttons.

    Note that we arbitrarily define a multipress as 'X press events in a single
    second'.

    """

    def __init__(self, hass, vantage_device, controller, name):
        self._hass = hass
        self._vantage_device = vantage_device
        self._controller = controller
        self._event_queue = collections.deque()
        self._event_queue_lock = threading.Lock()
        self._name = name

    def pressed(self):
        # First fire an event for the button press.  This lets users define
        # automations which react instantly to a button tap (instead of waiting
        # 1 second to count how many taps there were):
        time = self._vantage_device.extra_info['last_changed_timestamp']
        self._hass.bus.fire('vantage_button_pressed', {
            'button': self._name,
            'time': time
        })

        # Record when this press happened in _event_queue:
        self._event_queue_lock.acquire()
        try:
            self._event_queue.append(time)
        finally:
            self._event_queue_lock.release()

        # Check back one second from now to issue multipress events:
        t = threading.Timer(1.0, self.process_event_queue)
        t.start()

    def released(self):
        # Fire an event for the button release
        time = self._vantage_device.extra_info['last_changed_timestamp']
        self._hass.bus.fire('vantage_button_released', {
            'button': self._name,
            'time': time
        })

    def process_event_queue(self):
        """Count clicks and issue vantage_button_multipressed events.

        Since this is invoked once for every button press, and it is invoked at
        least 1.0 seconds after the press -- every button press should be
        removed from the queue and counted at most 1 second (plus episilon)
        after it is added to the queue.

        If the system gets bogged down, it may take a bit more time to invoke
        this.  Oh well.

        If threading.Timer invokes this too soon (it fails to wait 1.0 seconds),
        then this routine may just leave the press event in the queue for the
        next invocation (which may not happen until the user presses the button
        again).  Assume this will never (or at least, very very rarely) happen.

        """

        clicks = 0
        self._event_queue_lock.acquire()
        try:
            if self._event_queue:
                now = time.time()
                start_time = self._event_queue[0]
                if (now - start_time) >= 1.0:
                    while (self._event_queue and
                           (self._event_queue[0] - start_time) <= 1.0):
                        clicks += 1
                        self._event_queue.popleft()
        finally:
            self._event_queue_lock.release()

        if clicks > 0:
            self._hass.bus.fire('vantage_button_multipressed', {
                'clicks': clicks,
                'button': self._name,
                'time': start_time
            })
            # Recurse to empty the queue in the case where execution of this
            # routine was really delayed:
            self.process_event_queue()
