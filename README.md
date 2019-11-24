hass-vantage
============

By Greg J. Badros <badros@gmail.com>

For license information, see LICENSE -- Vantage systems control high voltage
electricity, you risk shock, fire, injury or death using this software.  Use
this at your own risk!

This is a custom component for the Vantage Infusion whole-home lighting system
for use with Home Assistant.

It relies on my pyvantage module (from PyPi at
https://pypi.org/project/pyvantage/ or github at
https://github.com/gjbadros/pyvantage).


Why?
====

You probably have a Vantage system because it is one of the best lighting
automation systems on the market.  It is super reliable, supports virtually all
types of lighting fixtures, and has excellent quality keypads.

It also integrates with many non-lighting things in your home -- but not all of
them.  Personally, I had trouble integrating Vantage with door locks, and found
that the visual programming language Vantage uses was making some automations I
wanted to make too challenging.

If you have something that is not supported by Vantage, you can either: (a)
replace it with something supported by Vantage; (b) write a driver for it; (c)
hire someone else to write a driver; or (d) use this Home Assistant integration!


Setup
=====

I use the following script to setup pyvantage and the vantage custom component.
You'll have to tweak it based on how you have Home Assistant set up.

```
    # First download pyvantage and add it to homeassistant.  Installs pyvantage
    # in the current directory and assumes home-assistant is in
    # ./home-assistant:

    git clone https://github.com/colohan/pyvantage.git
    cd pyvantage
    git remote add upstream https://github.com/gjbadros/pyvantage.git
    cd ..

    cd home-assistant
    python3 -m venv venv
    source venv/bin/activate

    # If we want to edit pyvantage, we install it from a local mirror of the git
    # repo:
    cd ../pyvantage
    pip3 install --editable .

    cd ../home-assistant
    script/setup

    # Now install the vantage custom component:

    cd ~/.homeassistant/custom_components
    git clone https://github.com/colohan/hass-vantage.git vantage
    cd vantage
    git remote add upstream https://github.com/gjbadros/hass-vantage.git
```


And add something like the following to configuration.yaml:

```
vantage:
  host: 192.168.0.123
  disable_cache: True
  username: !secret vantage_username
  password: !secret vantage_password
  exclude_areas: "SPARE RELAYS"
```

And add the following to secrets.yaml:

```
vantage_username: [my_username]
vantage_password: [my_password]
```

and then restart home assistant.

Note: The specified user must be in group Admin and have "Read State", "Write
State" and "Read Config" permissions to work.  See "Settings->Project Security"
in Vantage Design Center.

Note2: if your Vantage system is not set up with a username and password you can
elide the username: and password: lines in the configuration.yaml file, and skip
setting up secrets.yaml.  Or, just add a password to your Vantage!

Note3: if your Home Assistant can't talk to Vantage over the network, it can't
work.  If you have a firewall configure it to let the connections on ports 2001
and 3001 through.


Usage
=====

Now that you have the Vantage system set up, it is time to use it!

If you are new to using Home Assistant, you are going to use the default
Lovelace UI.  And you'll quickly find out that there is a huge list of Lights
and Badges cluttering up your UI as soon as you install the Vantage module.
This is because the typical Vantage install has a very large number of lights,
loads, and sensors, since it controls everything in the house, and Vantage users
tend to have larger houses.

  **WARNING**: At the top of the Light panel is a very tempting, innocuous
  looking switch.  It turns on (or off) *all* the lights in your home at the
  same time.  Turning on all your lights simultaneously IS A BAD IDEA.

  Why?  If you have LED lighting, the internal capacitors in those lights take a
  bunch of current to charge when you first turn them on.  If you turn on enough
  of them all on at once, the load spike may be large enough to pop several
  breakers or worse.

One of the first things you will be strongly tempted to do is manually configure
your Lovelace UI to clean out all the stuff you don't care about.  This is not a
bad idea.

So what has the Vantage component added to your home assistant?  A number of
things:

1.  For every light controlled by Vantage, a light.* entity.  Lights can be a
    dimmable or non-dimmable, color (DMX) or monochrome.
2.  For every switched load controlled by Vantage, a switch.* entity.
3.  For every window shade controlled by Vantage, a cover.* entity.
4.  For every motion sensor, contact sensor (such as a door opening sensor) or
    other binary sensor attached to Vantage, a sensor.* entity.
5.  Temperature, power and current sensors showing the status of the Infusion
    dimmer modules and their attached loads.
6.  For every light group defined by Vantage, a light.* entity.
7.  For every button on every keypad, a sensor.* entity showing whether the
    button is current pressed or not.
8.  For every keypad, a sensor.* entity saying which button on the keypad was
    pressed last.
9.  For every variable defined in Vantage, a sensor.* entity containing the
    current state of that variable.
10. Services for setting Vantage variables and calling Vantage tasks
    (vantage.set_variable, vantage.call_task, vantage.set_variable_vid, and
    vantage.call_task_vid).
11. Events which get fired whenever a keypad button is pressed
    (vantage_button_pressed, vantage_button_released,
    vantage_button_multipressed).


Leaving Stuff Out
=================

If you feel that Home Assistant is overwhelmed by all the Entities from Vantage
you are not going to immediately use, you can just leave them out.  Here are
some configuration options you can use:

```
  # Don't include Vantage buttons:
  exclude_buttons: True
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

  # Not sure what an "area" is, need to look into this.
  only_areas: ???
  exclude_areas: ???
```

If you are running Home Assistant on an Raspberry Pi, then the system might bog
down doing database writes to the sdcard once you start using it to control a
Vantage system.  Offloading the database to an external system (such as a server
running MariaDB) can improve performance dramatically.


Naming of Entities
==================

Every entity in Home Assistant needs a unique name.  In Vantage, objects don't
need unique names -- they all have a unique VID.

This Vantage component attempts to generate unique names by concatenating the
names of the levels of the object hierarchy in Vantage.  So a light in your
second floor master bath might create an Entity called
"light.second_floor_master_bath_vanity_light" with a friendly name of "Second
Floor-Master Bath-Vanity Light" (the friendly name is used by Lovelace in
displaying objects, the Entity name is what you use when you are coding up
automations).  If you have two objects with the same name (very common with
buttons, where multiple buttons may have similar names such as "On" and "Off"),
this module will just add the VID to the end.

These names are very long.  If you want shorter Entity names, you can do one of
the following:

1.  Use the Configuration->Entity Registry UI to rename your entities.  This can
    be tedious, and if you ever re-initialize Home Assistant's Entity registry
    (such as by following step 2 below) then you may lose these changes.

2.  Rename your objects in the Vantage Design Center.  The "Display Name" will
    override the "Name" field in Home Assistant if present (Note: only for Load
    objects, for keypads and motion sensors it does not).  Once you do this you
    need to set `disable_cache: True` in your `configuration.yaml`, erase the
    file `~/.homeassistant/.storage/core.entity_registry`, and restart Home
    Assistant to rebuild the entity registry.  You may renable the cache once
    Home Assistant has restarted once.

3.  Create mappings to rename objects in your `configuration.yaml`, like:

```
  name_mappings:
    - area: 'second floor'
      to: 2F
```

    Note that unless you delete the entity registry and rebuild it (as described
    in 2 above) this will only rename the friendly names of entities and not the
    entity name.

In some cases the Vantage component uses object names to infer functionality,
since the Vantage metadata makes it hard to determine.  If a light's name ends
in " COLOR" it is assumed to be a color load.  If the load type is "High Voltage
Relay" then it assumes it is a switch and not a light.


Grouping Lights
===============

Chances are you don't want to control each and every circuit from the Lovelace
UI.  You can group the Vantage lights into simpler lights using the "group"
plaform like this:

```
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



Power Sensors
=============

Infusion Dimmer modules have a neat feature which is not visible in Design
Center: they measure the power consumption of all of their lighting loads.  This
Vantage component gives you the data from your individual power sensors, you may
want to aggregate it into a single measure using some code similar to this:

```
sensor:
  - platform: template
    sensors:
      total_vantage_power:
        friendly_name: "Lighting Energy Usage"
        unit_of_measurement: 'W'
        value_template: "{{ states('sensor.power_sensor_line_d_365') | float + states('sensor.power_sensor_line_d_281') | float + states('sensor.power_sensor_line_d_175') | float + states('sensor.power_sensor_line_d_120') | float + states('sensor.power_sensor_line_d') | float + states('sensor.power_sensor_line_c_364') | float + states('sensor.power_sensor_line_c_280') | float + states('sensor.power_sensor_line_c_174') | float + states('sensor.power_sensor_line_c_119') | float + states('sensor.power_sensor_line_c') | float + states('sensor.power_sensor_line_b_363') | float + states('sensor.power_sensor_line_b_279') | float + states('sensor.power_sensor_line_b_173') | float + states('sensor.power_sensor_line_b_118') | float + states('sensor.power_sensor_line_b') | float + states('sensor.power_sensor_line_a') | float + states('sensor.power_sensor_line_a_117') | float + states('sensor.power_sensor_line_a_172') | float + states('sensor.power_sensor_line_a_278') | float + states('sensor.power_sensor_line_a_362') | float }}"
```


Not Supported (Yet?)
====================

There are things that Vantage can do which Home Assistant can't do (yet).  Here
is an incomplete list with workarounds:

  * Change the color, brightness or blink rate of the LED light on each keypad
    button.
        => Write a Vantage function to do this, invoke from Home Assistant
  * Dim lights in response to long button presses.
        => Configure the button to invoke the Dim Cycle routine on the Vantage
           controller, and then have Home Assistant events respond to the light
           brightness level changing.
  * Cause the keypads to make a tone.  (It appears that there is an interface to
    make a keypad start making a tone and stop making a tone, but not to have it
    play a tone for a specified duration...)
        => Write a Vantage function to do this, invoke from Home Assistant
  * Enable/disable Vacation mode on the Vantage.
        => Write a Vantage function to do this, invoke from Home Assistant
  * Invoke Home Assistant actions or routines from Vantage procedures (this
    component allows Home Assistant to control Vantage, not Vantage to control
    Home Assistant).
        => Use a variable as a signal: increment a Vantage variable from the
           Vantage function, and then trigger Home Assistant events based on the
           variable changing.  (This is a real kludge, but it seems to work.)
  * Lock/unlock Vantage objects.  (Why?)
        => Write a Vantage function to do this, invoke from Home Assistant
  * Interface fully with A/V components, thermostats, alarm systems, or other
    non-lighting devices you might have attached to your Vantage system.
        => Hook them up to Home Assistant instead.  Alternatively, write a
           Vantage function to do this, invoke from Home Assistant.

An example of this last item: one of the early users of this Vantage module had
an Elk alarm system which was wired to their Vantage Infusion controller through
a serial cable.  The Elk driver for Vantage worked, but awkward to use.  One
problem: it didn't have different states for an alarm being armed or simply in
the process of arming -- which made it hard to write routines to only run if the
alarm was armed.  The Home Assistant Elk driver is more full featured, and makes
creating such automations easy.

As a result, this user chose to create a new serial cable to plug the Elk
directly into their Home Assistant computer (alternatively, they could have
spent more money to buy the Elk IP interface, which is also known to work well).
