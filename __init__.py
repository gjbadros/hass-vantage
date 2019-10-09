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

DOMAIN = "vantage"

_LOGGER = logging.getLogger(__name__)

VANTAGE_CONTROLLER = "vantage_controller"
VANTAGE_DEVICES = "vantage_devices"

CONF_ONLY_AREAS = "only_areas"
CONF_DISABLE_CACHE = "disable_cache"
CONF_EXCLUDE_AREAS = "exclude_areas"
CONF_EXCLUDE_BUTTONS = "exclude_buttons"
CONF_EXCLUDE_CONTACTS = "exclude_contacts"
CONF_EXCLUDE_KEYPADS = "exclude_keypads"
CONF_EXCLUDE_VARIABLES = "exclude_variables"
CONF_INCLUDE_UNDERSCORE_VARIABLES = "include_underscore_variables"
CONF_EXCLUDE_NAME_SUBSTRING = "exclude_name_substring"
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
                vol.Optional(CONF_EXCLUDE_BUTTONS): cv.boolean,
                vol.Optional(CONF_EXCLUDE_CONTACTS): cv.boolean,
                vol.Optional(CONF_EXCLUDE_KEYPADS): cv.boolean,
                vol.Optional(CONF_EXCLUDE_VARIABLES): cv.boolean,
                vol.Optional(CONF_INCLUDE_UNDERSCORE_VARIABLES): cv.boolean,
                vol.Optional(CONF_DISABLE_CACHE): cv.boolean,  # FIXME
                vol.Optional(CONF_NAME_MAPPINGS): NAME_MAPPINGS_SCHEMA,
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
        area = mapping[CONF_AREA]
        to = mapping[CONF_TO]
        answer[area] = to
        _LOGGER.debug("Adding mapping of '%s' to '%s'", area, to)
    return answer


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
        fn = functools.partial(hass.data[VANTAGE_CONTROLLER].set_variable, name, value)
        await hass.async_add_executor_job(fn)

    async def async_handle_call_task_vid(call):
        vid = call.data.get("vid")
        if vid is None:
            raise Exception("Missing vid on vantage.call_task_vid")
        _LOGGER.debug("Called CALL_TASK_VID service: %s", str(call))
        fn = functools.partial(hass.data[VANTAGE_CONTROLLER].call_task_vid, vid)
        await hass.async_add_executor_job(fn)

    async def async_handle_call_task(call):
        name = call.data.get("name")
        if name is None:
            raise Exception("Missing name on vantage.call_task")
        _LOGGER.debug("Called CALL_TASK service: %s", str(call))
        fn = functools.partial(hass.data[VANTAGE_CONTROLLER].call_task, name)
        await hass.async_add_executor_job(fn)

    hass.data[VANTAGE_CONTROLLER] = None
    hass.data[VANTAGE_DEVICES] = {"light": [], "cover": [], "sensor": [], "switch": []}

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
    if not (config_name_mappings is None):
        name_mappings = mappings_from(config_name_mappings)

    username = None
    password = None
    if CONF_USERNAME in config:
        username = config[CONF_USERNAME]
        password = config[CONF_PASSWORD]
        _LOGGER.info("Username is %s", username)

    hass.data[VANTAGE_CONTROLLER] = Vantage(
        config[CONF_HOST],
        username,
        password,
        only_areas,
        exclude_areas,
        3001,
        2001,
        name_mappings,
    )

    vc = hass.data[VANTAGE_CONTROLLER]

    await hass.async_add_executor_job(
        functools.partial(vc.load_xml_db, config.get(CONF_DISABLE_CACHE, False))
    )
    await hass.async_add_executor_job(vc.connect)
    _LOGGER.debug("Connected to main repeater at %s", config[CONF_HOST])

    def is_excluded_name(entity):
        for ns in set_exclude_name_substring:
            if ns in entity.name:
                _LOGGER.debug(
                    "skipping %s because exclude_name_substring has '%s'", entity, ns
                )
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
            hass.data[VANTAGE_DEVICES]["cover"].append((area.name, output))
        elif output.kind == "RELAY":
            hass.data[VANTAGE_DEVICES]["switch"].append((area.name, output))
        elif output.kind == "LIGHT":
            _LOGGER.debug("adding light vid=%s to area=%s", output._vid, area.name)
            hass.data[VANTAGE_DEVICES]["light"].append((area.name, output))
        elif output.kind == "GROUP":
            _LOGGER.debug(
                "adding group (of lights/relays) vid=%s to area=%s",
                output._vid,
                area.name,
            )
            hass.data[VANTAGE_DEVICES]["light"].append((area.name, output))

    if not config.get(CONF_EXCLUDE_VARIABLES):
        for var in vc.variables:
            if not is_excluded_name(var):
                if config.get(
                    CONF_INCLUDE_UNDERSCORE_VARIABLES
                ) or not var.name.startswith("_"):
                    hass.data[VANTAGE_DEVICES]["sensor"].append((None, var))

    # buttons and dry contacts are are sensors too:
    # Their value is the name of the last action on them
    for button in vc.buttons:
        if (button.kind == "button" and not config.get(CONF_EXCLUDE_BUTTONS)) or (
            button.kind == "contact" and not config.get(CONF_EXCLUDE_CONTACTS)
        ):
            if should_keep_for_area_vid(button.area) and not is_excluded_name(button):
                hass.data[VANTAGE_DEVICES]["sensor"].append((None, button))

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

    hass.services.async_register(
        DOMAIN, "set_variable_vid", async_handle_set_variable_vid
    )
    hass.services.async_register(DOMAIN, "call_task_vid", async_handle_call_task_vid)
    hass.services.async_register(DOMAIN, "set_variable", async_handle_set_variable)
    hass.services.async_register(DOMAIN, "call_task", async_handle_call_task)
    return True


class VantageDevice(Entity):
    """Representation of a Vantage device entity."""

    def __init__(self, area_name, vantage_device, controller):
        """Initialize the device."""
        self._vantage_device = vantage_device
        self._controller = controller
        self._area_name = area_name
        self._unique_id = "vantagevid-{}".format(vantage_device.vid)

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register callbacks."""
        self.hass.async_add_job(
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
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def kind(self):
        """The vantage device kind."""
        return self._vantage_device.kind

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attr = self._vantage_device._extra_info.copy()
        attr["Vantage Integration ID"] = self._vantage_device.id
        if self.kind is not None:
            attr["Vantage Kind"] = self.kind
        return attr
