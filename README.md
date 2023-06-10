# hass-vantage

By Greg J. Badros <badros@gmail.com>

For license information, see [LICENSE](./LICENSE)

Vantage systems control high voltage electricity, you risk shock, fire, injury or death using this software. Use this at your own risk!

This is a custom component for the Vantage Infusion whole-home lighting system for use with Home Assistant.

It relies on my pyvantage module (from [PyPi](https://pypi.org/project/pyvantage/) or [GitHub](https://github.com/gjbadros/pyvantage)).

## Why?

You probably have a Vantage system because it is one of the best lighting automation systems on the market. It is super reliable, supports virtually all types of lighting fixtures, and has excellent quality keypads.

It also integrates with many non-lighting things in your home -- but not all of them. Personally, I had trouble integrating Vantage with door locks, and found that the visual programming language Vantage uses was making some automations I wanted to make too challenging.

If you have something that is not supported by Vantage, you can either:

- Replace it with something supported by Vantage.
- Write a driver for it.
- Hire someone else to write a driver.
- Or use this Home Assistant integration!

## Setup

Install the custom component in your HA `/config/custom_components/vantage` directory.  
There are multiple ways to do this, following is an example:

```shell
# Change to your HA /config directory
ls -la

# Create a 3rd party directory
mkdir 3rdparty

# Download the custom component from GitHub
wget -O ./3rdparty/vantage.zip https://github.com/gjbadros/hass-vantage/archive/refs/heads/master.zip

# Extract zip contents
unzip ./3rdparty/vantage.zip -d ./3rdparty/vantage

# Copy to custom_components
mkdir -p custom_components/vantage
cp -r ./3rdparty/vantage/hass-vantage-master/custom_components/vantage/ ./custom_components/
```

## Configuration

And add something like the following to the HA configuration.yaml:

```yaml
vantage:
  host: 192.168.0.123
  # Optional, required if running a security enabled controller
  username: !secret vantage_username
  password: !secret vantage_password
  # Optional, set to True if running a SSL enabled controller
  use_ssl: True
  # Optional, see additional configuration options
  exclude_areas: "SPARE RELAYS"
```

And add the following to secrets.yaml:

```yaml
vantage_username: [my_username]
vantage_password: [my_password]
```

Configuration parameters:

- `host` (Required string): IP address or FQDN of the controller.
- `username` (Optional string): Username
- `password` (Optional string): Password
- `use_ssl` (Default `False`): Controllers running v4+ firmware supports SSL on ports 2010 and 3010, non-SSL ports are 2001 and 3001.
- `only_areas` (Optional comma separated string): Only include these areas, inverse of `exclude_areas` option.
- `enable_cache` (Default `False`): Read the configuration once and write it to a configuration file, read from the configuration file in future. If any changes are made to configuration in design Center the file must be manually deleted.
- `exclude_areas` (Optional comma separated string): Exclude these areas, inverse of `only_areas` option.
- `include_buttons` (Default `False`): Create sensors for every keypad button.
- `exclude_contacts` (Default `False`): Exclude contacts.
- `exclude_keypads` (Default `False`): Exclude keypads.
- `exclude_variables` (Default `False`): Exclude variables.
- `include_underscore_variables` (Default `False`): Include variables prefixed with `_`.
- `exclude_name_substring` (Optional comma separated string): Exclude objects with names matching substrings
- `log_communications` (Default `False`): Log controller communications.
- `num_connections` (Default `1`): Number of controller connections.
- `name_mappings`: See later example, array of area name re-mappings.

And then restart home assistant.

Notes:

- The specified `username` must be in group Admin and have "Read State", "Write State" and "Read Config" permissions to work. See "Settings->Project Security" in Vantage Design Center.
- If your Vantage system is not set up with a username and password you can elide the `username` and `password` lines in the configuration.yaml file, and skip setting up secrets.yaml. Or, just add a password to your Vantage!
- If your Home Assistant can't talk to Vantage over the network, it can't work. If you have a firewall configure it to let the connections on ports 2001/2010 and 3001/3010 through.

## Usage

Now that you have the Vantage system set up, it is time to use it!

If you are new to using Home Assistant, you are going to use the default Lovelace UI. And you'll quickly find out that there is a huge list of Lights and Badges cluttering up your UI as soon as you install the Vantage module. This is because the typical Vantage install has a very large number of lights, loads, and sensors, since it controls everything in the house, and Vantage users tend to have larger houses.

**WARNING**: At the top of the Light panel is a very tempting, innocuous looking switch. It turns on (or off) *all* the lights in your home at the same time. Turning on all your lights simultaneously IS A BAD IDEA.

Why? If you have LED lighting, the internal capacitors in those lights take a bunch of current to charge when you first turn them on. If you turn on enough of them all on at once, the load spike may be large enough to pop several breakers or worse.

One of the first things you will be strongly tempted to do is manually configure your Lovelace UI to clean out all the stuff you don't care about. This is not a bad idea.

So what has the Vantage component added to your home assistant?  A number of things:

- For every light controlled by Vantage, a `light.*` entity. Lights can be a dimmable or non-dimmable, color (DMX) or monochrome.
- For every switched load controlled by Vantage, a `switch.*` entity.
- For every window shade controlled by Vantage, a `cover.*` entity.
- For every motion sensor, contact sensor (such as a door opening sensor) or other binary sensor attached to Vantage, a `sensor.*` entity.
- Temperature, power and current sensors showing the status of the Infusion dimmer modules and their attached loads.
- For every light group defined by Vantage, a `light.*` entity.
- If enabled (set include_buttons to True to enable): for every button on every keypad, a `sensor.*` entity showing whether the button is current pressed or not.
- For every keypad, a `sensor.*` entity saying which button on the keypad was pressed last.
- For every variable defined in Vantage, a `sensor.*` entity containing the current state of that variable.
- Services for setting Vantage variables and calling Vantage tasks (`vantage.set_variable`, `vantage.call_task`, `vantage.set_variable_vid`, and `vantage.call_task_vid`).
- Events which get fired whenever a keypad button is pressed (`vantage_button_pressed`, `vantage_button_released`).

## Leaving Stuff Out

If you feel that Home Assistant is overwhelmed by all the Entities from Vantage you are not going to immediately use, you can just leave them out.  
Here are some configuration options you can use:

```yaml
  # Don't include Vantage contacts (such as motion sensors):
  exclude_contacts: True

  # Don't include keypads:
  exclude_keypads: True

  # Don't include Vantage variables:
  exclude_variables: True

  # Don't include any object with the string "DISABLED" or "BROKEN" in the name:
  exclude_name_substring: 'DISABLED,BROKEN'

  # Include variables which are prefixed with '_' (they are normally excluded):
  include_underscore_variables: True

  # Design Center organizes all Vantage objects into "areas" (floors/rooms),
  # these options let you limit which areas this integration pays attention to:
  only_areas: 'First floor'
  exclude_areas: 'Guest bathroom'
```

This driver can add a lot of devices to your home assistant system all at once which can bog your system down doing database writes. If you are running Home Assistant on a low-powered machine like a Raspberry Pi, then offloading the database to an external system (such as a server running MariaDB) can improve performance dramatically.

## Naming of Entities

Every entity in Home Assistant needs a unique name. In Vantage, objects don't need unique names -- they all have a unique VID.

This Vantage component attempts to generate unique names by concatenating the names of the levels of the object hierarchy in Vantage. So a light in your second floor master bath might create an Entity called `light.second_floor_master_bath_vanity_light` with a friendly name of `Second Floor-Master Bath-Vanity Light` (the friendly name is used by Lovelace in displaying objects, the Entity name is what you use when you are coding up automations).  If you have two objects with the same name (very common with buttons, where multiple buttons may have similar names such as `On` and `Off`), this module will just add the VID to the end.

These names are very long. If you want shorter Entity names, you can do one of the following:

- Use the Configuration->Entity Registry UI to rename your entities. This can be tedious, and if you ever re-initialize Home Assistant's Entity registry (such as by following step 2 below) then you may lose these changes.
- Rename your objects in the Vantage Design Center. The `Display Name` will override the `Name` field in Home Assistant if present (Note: only for Load objects, for keypads and motion sensors it does not). Once you do this you need to ensure that `enable_cache` is not set in your `configuration.yaml`, erase the file `~/.homeassistant/.storage/core.entity_registry`, and restart Home Assistant to rebuild the entity registry.
- Create mappings to rename objects in your `configuration.yaml`, like:

```yaml
  name_mappings:
    - area: 'second floor'
      to: 2F
```

Note that unless you delete the entity registry and rebuild it (as described above) this will only rename the friendly names of entities and not the entity name.

In some cases the Vantage component uses object names to infer functionality, since the Vantage metadata makes it hard to determine. If a light's name ends in `xxx COLOR` it is assumed to be a color load. If the load type is `High Voltage Relay` then it assumes it is a switch and not a light.

## Grouping Lights

Chances are you don't want to control each and every circuit from the Lovelace UI. You can group the Vantage lights into simpler lights using the `group` platform like this:

```yaml
light:
  - platform: group
    name: Basement Bath
    entities:
      - light.basement_bath_4_ba4_shower
      - light.basement_bath_4_ba4_vanity
      - light.basement_bath_4_ba4_wc_fan
      - light.basement_bath_4_ba4_wc_light
  - platform: group
    name: Guest Bedroom
    entities:
      - light.basement_bedroom_4_br4_ceiling_cans
      - light.basement_bedroom_4_br4_center_light
      - light.basement_bedroom_4_closet_br4_closet_storage
```

## Power Sensors

Infusion Dimmer modules have a neat feature which is not visible in Design Center: they measure the power consumption of all of their lighting loads. This Vantage component gives you the data from your individual power sensors, you may want to aggregate it into a single measure using some code similar to this:

```yaml
sensor:
  - platform: template
    sensors:
      total_vantage_power:
        friendly_name: "Lighting Energy Usage"
        unit_of_measurement: 'W'
        value_template: "{{ states('sensor.power_sensor_line_d_365') | float + states('sensor.power_sensor_line_d_281') | float + states('sensor.power_sensor_line_d_175') | float + states('sensor.power_sensor_line_d_120') | float + states('sensor.power_sensor_line_d') | float + states('sensor.power_sensor_line_c_364') | float + states('sensor.power_sensor_line_c_280') | float + states('sensor.power_sensor_line_c_174') | float + states('sensor.power_sensor_line_c_119') | float + states('sensor.power_sensor_line_c') | float + states('sensor.power_sensor_line_b_363') | float + states('sensor.power_sensor_line_b_279') | float + states('sensor.power_sensor_line_b_173') | float + states('sensor.power_sensor_line_b_118') | float + states('sensor.power_sensor_line_b') | float + states('sensor.power_sensor_line_a') | float + states('sensor.power_sensor_line_a_117') | float + states('sensor.power_sensor_line_a_172') | float + states('sensor.power_sensor_line_a_278') | float + states('sensor.power_sensor_line_a_362') | float }}"
```

## Not Supported (Yet?)

There are things that Vantage can do which Home Assistant can't do (yet). Here is an incomplete list with workarounds:

- Change the color, brightness or blink rate of the LED light on each keypad button.
  - Write a Vantage function to do this, invoke from Home Assistant
- Dim lights in response to long button presses.
  - Configure the button to invoke the Dim Cycle routine on the Vantage controller, and then have Home Assistant events respond to the light brightness level changing.
- Cause the keypads to make a tone. (It appears that there is an interface to make a keypad start making a tone and stop making a tone, but not to have it play a tone for a specified duration...)
  - Write a Vantage function to do this, invoke from Home Assistant
- Enable/disable Vacation mode on the Vantage.
  - Write a Vantage function to do this, invoke from Home Assistant
- Invoke Home Assistant actions or routines from Vantage procedures (this component allows Home Assistant to control Vantage, not Vantage to control Home Assistant).
  - Use a variable as a signal: increment a Vantage variable from the Vantage function, and then trigger Home Assistant events based on the variable changing. (This is a real kludge, but it seems to work.)
- Lock/unlock Vantage objects. (Why?)
  - Write a Vantage function to do this, invoke from Home Assistant
- Interface fully with A/V components, thermostats, alarm systems, or other non-lighting devices you might have attached to your Vantage system.
  - Hook them up to Home Assistant instead.  Alternatively, write a Vantage function to do this, invoke from Home Assistant.

An example of this last item: one of the early users of this Vantage module had an Elk alarm system which was wired to their Vantage Infusion controller through a serial cable. The Elk driver for Vantage worked, but awkward to use. One
problem: it didn't have different states for an alarm being armed or simply in the process of arming -- which made it hard to write routines to only run if the alarm was armed. The Home Assistant Elk driver is more full featured, and makes
creating such automations easy.

As a result, this user chose to create a new serial cable to plug the Elk directly into their Home Assistant computer (alternatively, they could have spent more money to buy the Elk IP interface, which is also known to work well).
