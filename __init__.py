"""
Component for interacting with a Vantage Infusion Controller system

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/vantage/
"""
import asyncio
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity

DOMAIN = 'vantage'

_LOGGER = logging.getLogger(__name__)

VANTAGE_CONTROLLER = 'vantage_controller'
VANTAGE_DEVICES = 'vantage_devices'

CONF_ONLY_AREAS = 'only_areas'
CONF_DISABLE_CACHE = 'disable_cache'
CONF_EXCLUDE_AREAS = 'exclude_areas'
CONF_EXCLUDE_BUTTONS = 'exclude_buttons'
CONF_EXCLUDE_CONTACTS = 'exclude_contacts'
CONF_EXCLUDE_KEYPADS = 'exclude_keypads'
CONF_NAME_MAPPINGS = 'name_mappings'
CONF_AREA = 'area'
CONF_TO = 'to'

NAME_MAPPING_SCHEMA = vol.Schema({
    vol.Required(CONF_AREA): cv.string,
    vol.Required(CONF_TO): cv.string})

NAME_MAPPINGS_SCHEMA = vol.All([NAME_MAPPING_SCHEMA])

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_ONLY_AREAS): cv.string,
        vol.Optional(CONF_EXCLUDE_AREAS): cv.string,
        vol.Optional(CONF_EXCLUDE_BUTTONS): cv.boolean,
        vol.Optional(CONF_EXCLUDE_CONTACTS): cv.boolean,
        vol.Optional(CONF_EXCLUDE_KEYPADS): cv.boolean,
        vol.Optional(CONF_DISABLE_CACHE): cv.boolean,  #FIXME
        vol.Optional(CONF_NAME_MAPPINGS): NAME_MAPPINGS_SCHEMA
    })
}, extra=vol.ALLOW_EXTRA)

def mappings_from(nm):
    """Return a dictionary of name mappings from the name_mappings config setting."""
    answer = {}
    for mapping in nm:
        area = mapping[CONF_AREA]
        to = mapping[CONF_TO]
        answer[area] = to
        _LOGGER.debug("Adding mapping of '%s' to '%s'", area, to)
    return answer


def setup(hass, base_config):
    """Set up the Vantage component."""
    from pyvantage import Vantage

    def handle_set_variable_vid(call):
        vid = call.data.get('vid')
        if vid is None:
            raise Exception("Missing vid on vantage.set_variable_vid")
        value = call.data.get('value')
        if value is None:
            raise Exception("Missing value on vantage.set_variable_vid")
        _LOGGER.info("Called SET_VARIABLE_VID service: %s", call)
        hass.data[VANTAGE_CONTROLLER].set_variable_vid(vid, value)

    def handle_set_variable(call):
        name = call.data.get('name')
        if name is None:
            raise Exception("Missing name on vantage.set_variable")
        value = call.data.get('value')
        if value is None:
            raise Exception("Missing value on vantage.set_variable")
        _LOGGER.info("Called SET_VARIABLE service: %s", str(call))
        hass.data[VANTAGE_CONTROLLER].set_variable(name, value)

    def handle_call_task_vid(call):
        id = call.data.get('vid')
        if id is None:
            raise Exception("Missing vid on vantage.call_task_vid")
        _LOGGER.info("Called CALL_TASK_VID service: %s", str(call))
        hass.data[VANTAGE_CONTROLLER].call_task_vid(id)

    def handle_call_task(call):
        name = call.data.get('name')
        if name is None:
            raise Exception("Missing name on vantage.call_task")
        _LOGGER.info("Called CALL_TASK service: %s", str(call))
        hass.data[VANTAGE_CONTROLLER].call_task(name)

    hass.data[VANTAGE_CONTROLLER] = None
    hass.data[VANTAGE_DEVICES] = {
        'light': [], 'cover': [], 'sensor': [], 'switch': []}

    config = base_config.get(DOMAIN)
    only_areas = config.get(CONF_ONLY_AREAS)
    exclude_areas = config.get(CONF_EXCLUDE_AREAS)

    if only_areas:
        only_areas = set(only_areas.split(","))
    if exclude_areas:
        exclude_areas = set(exclude_areas.split(","))

    name_mappings = mappings_from(config.get(CONF_NAME_MAPPINGS))

    hass.data[VANTAGE_CONTROLLER] = Vantage(
        config[CONF_HOST], config[CONF_USERNAME], config[CONF_PASSWORD],
        only_areas, exclude_areas, 3001, 2001,
        name_mappings)

    vc = hass.data[VANTAGE_CONTROLLER]

    vc.load_xml_db(config.get(CONF_DISABLE_CACHE, False))
    vc.connect()
    _LOGGER.info("Connected to main repeater at %s", config[CONF_HOST])


    def get_lineage_from_area(area):
        count = 0
        answer = [area.name]
        while area and count < 10:
            count += 1
            parent_vid = area.parent
            if parent_vid == 0:
                break
            area = vc._vid_to_area.get(parent_vid, None)
            if area:
                answer.append(area.name)
        return answer

    # Sort our devices into types
    for output in vc.outputs:
        _LOGGER.info("output = %s", output)
        area = vc._vid_to_area[output.area]
        # list of all the areas from child up to root
        area_lineage = get_lineage_from_area(area)
        _LOGGER.info("area = %s; lineage = %a", area.name, area_lineage)
        keep = not (only_areas or exclude_areas)
        if only_areas:
            for a in area_lineage:
                if a in only_areas:
                    _LOGGER.info("maybe including %s because of only_areas = %s",
                                 area.name, only_areas)
                    keep = True
                    break
            if keep and exclude_areas:
                for a in area_lineage:
                    if a in exclude_areas:
                        _LOGGER.info("but %s is in exclude_areas, so skipping", a)
                        keep = False
                        break
        elif exclude_areas:  # not specified include_areas
            keep = True
            for a in area_lineage:
                if a in exclude_areas:
                    _LOGGER.info("discarding %s because of exclude_areas = %s",
                                 area.name, exclude_areas)
                    keep = False
                    break
        if not keep:
            continue

        if output.kind == 'BLIND':
            hass.data[VANTAGE_DEVICES]['cover'].append((area.name, output))
        elif output.kind == 'RELAY':
            hass.data[VANTAGE_DEVICES]['switch'].append((area.name, output))
        elif output.kind == 'LIGHT':
            _LOGGER.debug("adding light vid=%s to area=%s", output._vid, area.name)
            hass.data[VANTAGE_DEVICES]['light'].append((area.name, output))
        elif output.kind == 'GROUP':
            _LOGGER.debug("adding group (of lights/relays) vid=%s to area=%s",
                          output._vid, area.name)
            hass.data[VANTAGE_DEVICES]['light'].append((area.name, output))


    for var in vc.variables:
        hass.data[VANTAGE_DEVICES]['sensor'].append((None, var))

    # buttons and dry contacts are are sensors too:
    # Their value is the name of the last action on them
    for button in vc.buttons:
        _LOGGER.debug("kind = %s, ceb = %s, cec = %s",
                      button.kind, config.get(CONF_EXCLUDE_BUTTONS),
                      config.get(CONF_EXCLUDE_CONTACTS))
        if ((button.kind == 'button' and not config.get(CONF_EXCLUDE_BUTTONS)) or
                (button.kind == 'contact' and not config.get(CONF_EXCLUDE_CONTACTS))):
            hass.data[VANTAGE_DEVICES]['sensor'].append((None, button))

    # and so are keypads.  Their value is the name of the last button pressed
    if not config.get(CONF_EXCLUDE_KEYPADS):
        for keypad in vc.keypads:
            hass.data[VANTAGE_DEVICES]['sensor'].append((None, keypad))

    for component in ('light', 'cover', 'sensor', 'switch'):
        discovery.load_platform(hass, component, DOMAIN, None, base_config)

    hass.services.register(DOMAIN, 'set_variable_vid', handle_set_variable_vid)
    hass.services.register(DOMAIN, 'call_task_vid', handle_call_task_vid)
    hass.services.register(DOMAIN, 'set_variable', handle_set_variable)
    hass.services.register(DOMAIN, 'call_task', handle_call_task)
    return True

class VantageDevice(Entity):
    """Representation of a Vantage device entity."""

    def __init__(self, area_name, vantage_device, controller):
        """Initialize the device."""
        self._vantage_device = vantage_device
        self._controller = controller
        self._area_name = area_name
        self._unique_id = 'vantagevid-{}'.format(vantage_device.vid)

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register callbacks."""
        self.hass.async_add_job(
            self._controller.subscribe,
            self._vantage_device,
            self._update_callback
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
    def device_state_attributes(self):
        """Return the state attributes."""
        attr = {}
        attr['Vantage Integration ID'] = self._vantage_device.id
        return attr
