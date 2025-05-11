"""
Component for interacting with a Vantage Infusion Controller system

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/vantage/
"""
import asyncio
import logging
import functools

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity
from homeassistant.core import Event
from homeassistant.util import slugify

DOMAIN = "vantage"

_LOGGER = logging.getLogger(__name__)

VANTAGE_CONTROLLER = "vantage_controller"
VANTAGE_DEVICES = "vantage_devices"

CONF_USE_SSL = "use_ssl"
CONF_ONLY_AREAS = "only_areas"
CONF_ENABLE_CACHE = "enable_cache"
CONF_EXCLUDE_AREAS = "exclude_areas"
CONF_INCLUDE_BUTTONS = "include_buttons"
CONF_EXCLUDE_CONTACTS = "exclude_contacts"
CONF_EXCLUDE_KEYPADS = "exclude_keypads"
CONF_EXCLUDE_VARIABLES = "exclude_variables"
CONF_INCLUDE_UNDERSCORE_VARIABLES = "include_underscore_variables"
CONF_EXCLUDE_NAME_SUBSTRING = "exclude_name_substring"
CONF_LOG_COMMUNICATIONS = "log_communications"
CONF_NUM_CONNECTIONS = "num_connections"
CONF_NAME_MAPPINGS = "name_mappings"
CONF_AREA = "area"
CONF_TO = "to"

NAME_MAPPING_SCHEMA = vol.Schema(
    {vol.Required(CONF_AREA): cv.string, vol.Required(CONF_TO): cv.string}
)

NAME_MAPPINGS_SCHEMA = vol.All([NAME_MAPPING_SCHEMA])

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_USERNAME): cv.string,
                vol.Optional(CONF_ONLY_AREAS): cv.string,
                vol.Optional(CONF_EXCLUDE_AREAS): cv.string,
                vol.Optional(CONF_EXCLUDE_NAME_SUBSTRING): cv.string,
                vol.Optional(CONF_LOG_COMMUNICATIONS, default=False): cv.boolean,
                vol.Optional(CONF_NUM_CONNECTIONS, default=1): cv.positive_int,
                vol.Optional(CONF_INCLUDE_BUTTONS, default=False): cv.boolean,
                vol.Optional(CONF_EXCLUDE_CONTACTS, default=False): cv.boolean,
                vol.Optional(CONF_EXCLUDE_KEYPADS, default=False): cv.boolean,
                vol.Optional(CONF_EXCLUDE_VARIABLES, default=False): cv.boolean,
                vol.Optional(CONF_INCLUDE_UNDERSCORE_VARIABLES,
                             default=False): cv.boolean,
                vol.Optional(CONF_ENABLE_CACHE,
                             default=False): cv.boolean,  # FIXME
                vol.Optional(CONF_NAME_MAPPINGS): NAME_MAPPINGS_SCHEMA,
                vol.Optional(CONF_USE_SSL, default=False): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def mappings_from(nm):
    """Return a dictionary of name mappings
    from the name_mappings config setting."""
    answer = {}
    for mapping in nm:
        area = mapping[CONF_AREA].lower()
        to = mapping[CONF_TO]
        answer[area] = to
        _LOGGER.debug("Adding mapping of '%s' to '%s'", area, to)
    return answer


def handle_dump_memory():
    """Dump memory using muppy to look for a leak"""
    from pympler import muppy, summary
    from collections import Counter
    import json
    import random

    _LOGGER.warning("vantage.dump_memory started")
    all_objects = muppy.get_objects()
    sum1 = summary.summarize(all_objects)
    summary.print_(sum1)
    _LOGGER.warning("vantage.dump_memory summary done")
    events = [e for e in all_objects if isinstance(e, Event)]
    event_types = [e.event_type for e in events]
    c = Counter(event_types)
    _LOGGER.warning("event_types: %s", json.dumps(c.most_common()))
    for e in events:
        if e.event_type == 'call_service':
            if random.randint(0, 99) == 2:
                _LOGGER.warning("event_type call_service, data = %s",
                                json.dumps(e.data))
                _LOGGER.warning("context =  %s", e.context)
    _LOGGER.warning("vantage.dump_memory completed")


def button_pressed(hass, button):
    """Generate HASS bus events for button presses and releases."""
    payload = {
        'button':        slugify(button.name),
        'button_vid':    button.vid,
        'button_number': button.number,
    }
    if button._keypad is not None:
        payload['keypad_name'] = slugify(button.keypad_name)
        payload['keypad_vid'] = button.keypad_vid

    if button.value == "PRESS" or button.value == "Violated":
        hass.bus.fire('vantage_button_pressed', payload)
    elif button.value == "RELEASE" or button.value == "Normal":
        hass.bus.fire('vantage_button_released', payload)
    else:
        _LOGGER.warning("Unexpected state for button %s: %s",
                        button.name, button.value)


async def async_setup(hass, base_config):
    """Set up the Vantage component."""
    from pyvantage import Vantage

    async def async_handle_set_variable_vid(call):
        vid = call.data.get("vid")
        if vid is None:
            raise Exception("Missing vid on vantage.set_variable_vid")
        value = call.data.get("value")
        if value is None:
            raise Exception("Missing value on vantage.set_variable_vid")
        _LOGGER.debug("Called SET_VARIABLE_VID service: %s", call)
        fn = functools.partial(
            hass.data[VANTAGE_CONTROLLER].set_variable_vid, vid, value
        )
        await hass.async_add_executor_job(fn)

    async def async_handle_set_variable(call):
        name = call.data.get("name")
        if name is None:
            raise Exception("Missing name on vantage.set_variable")
        value = call.data.get("value")
        if value is None:
            raise Exception("Missing value on vantage.set_variable")
        _LOGGER.debug("Called SET_VARIABLE service: %s", str(call))
        fn = functools.partial(hass.data[VANTAGE_CONTROLLER].set_variable,
                               name, value)
        await hass.async_add_executor_job(fn)

    async def async_handle_call_task_vid(call):
        vid = call.data.get("vid")
        if vid is None:
            raise Exception("Missing vid on vantage.call_task_vid")
        _LOGGER.debug("Called CALL_TASK_VID service: %s", str(call))
        fn = functools.partial(hass.data[VANTAGE_CONTROLLER].call_task_vid,
                               vid)
        await hass.async_add_executor_job(fn)

    async def async_handle_call_task(call):
        name = call.data.get("name")
        if name is None:
            raise Exception("Missing name on vantage.call_task")
        _LOGGER.debug("Called CALL_TASK service: %s", str(call))
        fn = functools.partial(hass.data[VANTAGE_CONTROLLER].call_task, name)
        await hass.async_add_executor_job(fn)

    async def async_handle_dump_memory(call):
        await hass.async_add_executor_job(handle_dump_memory)

    def button_update_callback(device):
        """Run when invoked by pyvantage when the device state changes."""
        button_pressed(hass, device)

    hass.services.async_register(
        DOMAIN, "set_variable_vid", async_handle_set_variable_vid
    )
    hass.services.async_register(DOMAIN, "call_task_vid", async_handle_call_task_vid)
    hass.services.async_register(DOMAIN, "set_variable", async_handle_set_variable)
    hass.services.async_register(DOMAIN, "call_task", async_handle_call_task)
    hass.services.async_register(DOMAIN, "dump_memory", async_handle_dump_memory)

    hass.data[VANTAGE_CONTROLLER] = None
    hass.data[VANTAGE_DEVICES] = {"light": [], "cover": [],
                                  "sensor": [], "switch": []}

    config = base_config.get(DOMAIN)
    only_areas = config.get(CONF_ONLY_AREAS)
    exclude_areas = config.get(CONF_EXCLUDE_AREAS)
    exclude_name_substring = config.get(CONF_EXCLUDE_NAME_SUBSTRING)
    set_exclude_name_substring = set()

    if only_areas:
        only_areas = set(only_areas.split(","))
    if exclude_areas:
        exclude_areas = set(exclude_areas.split(","))
    if exclude_name_substring:
        set_exclude_name_substring = set(exclude_name_substring.split(","))
        _LOGGER.debug("excluded_names = %s", set_exclude_name_substring)

    config_name_mappings = config.get(CONF_NAME_MAPPINGS)
    name_mappings = None
    if config_name_mappings is not None:
        name_mappings = mappings_from(config_name_mappings)

    username = None
    password = None
    if CONF_USERNAME in config:
        username = config[CONF_USERNAME]
        password = config[CONF_PASSWORD]
        _LOGGER.info("Username is %s", username)

    use_ssl_connection = config.get(CONF_USE_SSL, False)

    hass.data[VANTAGE_CONTROLLER] = Vantage(
        config[CONF_HOST],
        username,
        password,
        only_areas,
        exclude_areas,
        3010 if use_ssl_connection else 3001,
        2010 if use_ssl_connection else 2001,
        name_mappings,
        None,
        config.get(CONF_LOG_COMMUNICATIONS),
        config.get(CONF_NUM_CONNECTIONS),
        use_ssl=use_ssl_connection
    )

    vc = hass.data[VANTAGE_CONTROLLER]

    await hass.async_add_executor_job(
        functools.partial(vc.load_xml_db,
                          not(config.get(CONF_ENABLE_CACHE, False)),
                          hass.config.config_dir)
    )
    await hass.async_add_executor_job(vc.connect)
    _LOGGER.debug("Connected to main repeater at %s", config[CONF_HOST])

    def is_excluded_name(entity):
        for ns in set_exclude_name_substring:
            if ns in entity.name:
                _LOGGER.debug(
                    "skipping %s because exclude_name_substring has '%s'",
                    entity, ns)
                return True
        return False

    def get_lineage_from_area(area):
        count = 0
        answer = [area.name]
        while area and count < 10:
            count += 1
            parent_vid = area.parent
            if parent_vid == 0:
                break
            area = vc._vid_to_area.get(parent_vid)
            if area:
                answer.append(area.name)
        return answer

    def should_keep_for_area_vid(area_vid):
        area = vc._vid_to_area.get(area_vid)
        if not area:
            # no area, then we omit this if only_areas was specified,
            # and include it (since it can't match an exclude_areas)
            # otherwise
            return not only_areas
        return should_keep_for_area(area)

    def should_keep_for_area(area):
        # list of all the areas from child up to root
        area_lineage = get_lineage_from_area(area)
        _LOGGER.debug("area = %s; lineage = %a", area.name, area_lineage)
        keep = not (only_areas or exclude_areas)
        if only_areas:
            for a in area_lineage:
                if a in only_areas:
                    _LOGGER.debug(
                        "maybe including %s " "because of only_areas = %s",
                        area.name,
                        only_areas,
                    )
                    keep = True
                    break
            if keep and exclude_areas:
                for a in area_lineage:
                    if a in exclude_areas:
                        _LOGGER.debug(
                            "button %s is in exclude_areas," " so skipping", a
                        )
                        keep = False
                        break
        elif exclude_areas:  # not specified include_areas
            keep = True
            for a in area_lineage:
                if a in exclude_areas:
                    _LOGGER.debug(
                        "discarding %s because exclude_areas = %s",
                        area.name,
                        exclude_areas,
                    )
                    keep = False
                    break
        return keep

    # Sort our devices into types
    for output in vc.outputs:
        _LOGGER.debug("output = %s", output)
        area = vc._vid_to_area[output.area]
        keep = should_keep_for_area(area)
        if not keep:
            continue
        if is_excluded_name(output):
            continue

        if output.kind == "BLIND":
            _LOGGER.debug("adding blind %s to area=%s", output, area.name)
            hass.data[VANTAGE_DEVICES]["cover"].append((area.name, output))
        elif output.kind == "RELAY":
            _LOGGER.debug("adding switch %s to area=%s", output, area.name)
            hass.data[VANTAGE_DEVICES]["switch"].append((area.name, output))
        elif output.kind == "LIGHT":
            _LOGGER.debug("adding light %s to area=%s", output, area.name)
            hass.data[VANTAGE_DEVICES]["light"].append((area.name, output))
        elif output.kind == "GROUP":
            _LOGGER.debug(
                "adding group (of lights/relays) %s to area=%s",
                output,
                area.name,
            )
            hass.data[VANTAGE_DEVICES]["light"].append((area.name, output))

    if not config.get(CONF_EXCLUDE_VARIABLES):
        for var in vc.variables:
            if not is_excluded_name(var):
                if config.get(
                    CONF_INCLUDE_UNDERSCORE_VARIABLES
                ) or not var.name.startswith("_"):
                    if var.kind == 'variable_bool' and not var.name.lower().endswith("_p"):
                        dom = "switch"
                    else:
                        dom = "sensor"
                    hass.data[VANTAGE_DEVICES][dom].append((None, var))

    # buttons and dry contacts are are sensors too:
    # Their value is the name of the last action on them
    for button in vc.buttons:
        if (button.kind == "button" and config.get(CONF_INCLUDE_BUTTONS)) or (
            button.kind == "contact" and not config.get(CONF_EXCLUDE_CONTACTS)
        ):
            if should_keep_for_area_vid(button.area) and not is_excluded_name(button):
                hass.data[VANTAGE_DEVICES]["sensor"].append((None, button))
        if (button.kind == "button" and not config.get(CONF_INCLUDE_BUTTONS)):
            if should_keep_for_area_vid(button.area) and not is_excluded_name(button):
                hass.async_add_executor_job(vc.subscribe, button, button_update_callback)

    for sensor in vc.sensors:
        if should_keep_for_area_vid(sensor.area) and not is_excluded_name(sensor):
            hass.data[VANTAGE_DEVICES]["sensor"].append((sensor._area, sensor))

    # and so are keypads.  Their value is the name of the last button pressed
    if not config.get(CONF_EXCLUDE_KEYPADS):
        for keypad in vc.keypads:
            if should_keep_for_area_vid(keypad.area) and not is_excluded_name(keypad):
                hass.data[VANTAGE_DEVICES]["sensor"].append((None, keypad))

    for component in ("light", "cover", "sensor", "switch"):
        await discovery.async_load_platform(hass, component, DOMAIN, None, base_config)

    return True


class VantageDevice(Entity):
    """Representation of a Vantage device entity.

    This is the base class for all the different types of
    HASS objects, each of which will also descend from their
    object-specific HASS base class."""

    _attr_should_poll = False

    def __init__(self, area_name, vantage_device, controller):
        """Initialize the device."""

        self._vantage_device = vantage_device
        self._controller = controller
        self._area_name = area_name
        self._unique_id = "vantagevid-{}".format(vantage_device.vid)
        self._unit_of_measurement = None
        self._device_class = None

    async def async_added_to_hass(self):
        """Register callbacks."""
        # this was async_add_job, but see: https://developers.home-assistant.io/blog/2024/03/13/deprecate_add_run_job/
        self.hass.async_add_executor_job(
            self._controller.subscribe, self._vantage_device, self._update_callback
        )

    def _update_callback(self, _device):
        """Run when invoked by pyvantage when the device state changes."""
        self.schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of the device."""
        return self._vantage_device.name

    @property
    def unique_id(self):
        """Unique ID of Vantage device - uses vid."""
        return self._unique_id

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement for this sensor."""
        return self._unit_of_measurement

    @property
    def device_class(self):
        """Return the device class for this sensor."""
        return self._device_class


    @property
    def kind(self):
        """The vantage device kind."""
        return self._vantage_device.kind

    @property
    def extra_state_attributes(self):
        """Return the extra state attributes."""
        attr = self._vantage_device._extra_info.copy()
        attr["vantage_id"] = self._vantage_device.id
        if self.kind is not None:
            attr["vantage_kind"] = self.kind
        if self.unit_of_measurement is not None:
            attr["unit_of_measurement"] = self.unit_of_measurement
        return attr
