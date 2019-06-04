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

REQUIREMENTS = ['pyvantage==0.0.10']

DOMAIN = 'vantage'

_LOGGER = logging.getLogger(__name__)

VANTAGE_CONTROLLER = 'vantage_controller'
VANTAGE_DEVICES = 'vantage_devices'

CONF_ONLY_AREAS = 'only_areas'
CONF_EXCLUDE_AREAS = 'exclude_areas'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_ONLY_AREAS): cv.string,
        vol.Optional(CONF_EXCLUDE_AREAS): cv.string,
        vol.Optional("disable_cache"): cv.boolean,  #FIXME
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, base_config):
    """Set up the Vantage component."""
    from pyvantage import Vantage

    def handle_set_variable_vid(call):
        id = call.data.get('vid')
        if id == None:
            raise Exception("Missing vid on vantage.set_variable_vid")
        value = call.data.get('value')
        if value == None:
            raise Exception("Missing value on vantage.set_variable_vid")
        _LOGGER.info("Called SET_VARIABLE_VID service: " + str(call))
        hass.data[VANTAGE_CONTROLLER].set_variable_vid(id, value)

    def handle_set_variable(call):
        name = call.data.get('name')
        if name == None:
            raise Exception("Missing name on vantage.set_variable")
        value = call.data.get('value')
        if value == None:
            raise Exception("Missing value on vantage.set_variable")
        _LOGGER.info("Called SET_VARIABLE service: " + str(call))
        hass.data[VANTAGE_CONTROLLER].set_variable(name, value)
        
    def handle_call_task_vid(call):
        id = call.data.get('vid')
        if id == None:
            raise Exception("Missing vid on vantage.call_task_vid")
        _LOGGER.info("Called CALL_TASK_VID service: " + str(call))
        hass.data[VANTAGE_CONTROLLER].call_task_vid(id)

    def handle_call_task(call):
        name = call.data.get('name')
        if name == None:
            raise Exception("Missing name on vantage.call_task")
        _LOGGER.info("Called CALL_TASK service: " + str(call))
        hass.data[VANTAGE_CONTROLLER].call_task(name)
        
    hass.data[VANTAGE_CONTROLLER] = None
    hass.data[VANTAGE_DEVICES] = {'light': [], 'cover': [], 'sensor': [], 'switch': []}

    config = base_config.get(DOMAIN)
    only_areas = config.get(CONF_ONLY_AREAS, None)
    exclude_areas = config.get(CONF_EXCLUDE_AREAS, None)

    if only_areas:
        only_areas = set(only_areas.split(","))
    if exclude_areas:
        exclude_areas = set(exclude_areas.split(","))
        
    name_mappings = {}
    name_mappings['main house'] = 'MH'
    name_mappings['office'] = 'MHO'
    name_mappings['pool house'] = 'PH'
    name_mappings['guest house'] = 'GH'
    name_mappings['upper floor'] = 'U'
    name_mappings['main floor'] = 'M'
    name_mappings['basement'] = 'B'
    name_mappings['outside'] = 'OUT'
    name_mappings['0-10v relays'] = True # means to skip

    hass.data[VANTAGE_CONTROLLER] = Vantage(
        config[CONF_HOST], config[CONF_USERNAME], config[CONF_PASSWORD],
        only_areas, exclude_areas, 3001, 2001,
        name_mappings)

    vc = hass.data[VANTAGE_CONTROLLER]

    vc.load_xml_db(config.get("disable_cache", False))
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
        _LOGGER.info("output = " + str(output))
        area = vc._vid_to_area[output.area]
        # list of all the areas from child up to root
        area_lineage = get_lineage_from_area(area)
        _LOGGER.info("area = " + area.name + "; lineage = " + str(area_lineage))
        keep = not (only_areas or exclude_areas)
        if only_areas:
            for a in area_lineage:
                if a in only_areas:
                    _LOGGER.info("maybe including " + area.name +
                                 " because of only_areas = " + str(only_areas))
                    keep = True
                    break
            if keep and exclude_areas:
                for a in area_lineage:
                    if a in exclude_areas:
                        _LOGGER.info("but " + a + " is in exclude_areas, so skipping")
                        keep = False
                        break
        elif exclude_areas:  # not specified include_areas
            keep = True
            for a in area_lineage:
                if a in exclude_areas:
                    _LOGGER.info("discarding " + area.name +
                                 " because of exclude_areas = " + str(exclude_areas))
                    keep = False
                    break
        if not keep:
            continue
        
        if output.type == 'BLIND':
            hass.data[VANTAGE_DEVICES]['cover'].append((area.name, output))
        elif output.type == 'RELAY':
            hass.data[VANTAGE_DEVICES]['switch'].append((area.name, output))
        elif output.type == 'LIGHT':
            _LOGGER.debug("adding light vid=%s to area=%s", output._vid, area.name)
            hass.data[VANTAGE_DEVICES]['light'].append((area.name, output))
        elif output.type == 'GROUP':
            _LOGGER.debug("adding group (of lights/relays) vid=%s to area=%s", output._vid, area.name)
            hass.data[VANTAGE_DEVICES]['light'].append((area.name, output))


    for var in vc.variables:
        hass.data[VANTAGE_DEVICES]['sensor'].append((None, var))

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
            self._controller.subscribe, self._vantage_device,
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
