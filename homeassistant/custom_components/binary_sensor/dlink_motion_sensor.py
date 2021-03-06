"""
Support for D-Link motion sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.dlink_motion_sensor/
"""
import asyncio
import logging
from datetime import timedelta, datetime

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_NAME, CONF_PASSWORD, CONF_USERNAME, CONF_HOST, CONF_TIMEOUT)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['PySimpleSOAP==1.16']

DEFAULT_NAME = 'D-Link Motion Sensor'
DEFAULT_USERNAME = 'Admin'
DEFAULT_TIMEOUT = 35

SCAN_INTERVAL = timedelta(seconds=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the D-Link motion sensor."""
    from .dlink_new import HNAPClient, MotionSensor, NanoSOAPClient, ACTION_BASE_URL

    soap = NanoSOAPClient(
        config.get(CONF_HOST),
        ACTION_BASE_URL,
        loop=hass.loop,
        session=async_get_clientsession(hass))

    client = HNAPClient(
        soap,
        config.get(CONF_USERNAME),
        config.get(CONF_PASSWORD),
        loop=hass.loop)

    motion_sensor = DlinkMotionSensor(
        config.get(CONF_NAME),
        config.get(CONF_TIMEOUT),
        MotionSensor(client))

    async_add_devices([motion_sensor], update_before_add=True)


class DlinkMotionSensor(BinarySensorDevice):
    """Representation of a D-Link motion sensor."""

    def __init__(self, name, timeout, motion_sensor):
        """Initialize the D-Link motion binary sensor."""
        self._name = name
        self._timeout = timeout
        self._motion_sensor = motion_sensor
        self._on = False
        self._times = 0

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._on

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return 'motion'

    @asyncio.coroutine
    def async_update(self):
        """Get the latest data and updates the states."""
        try:
            if self._times > 6000:
                self._times = 0
                yield from self._motion_sensor.reboot()
                last_trigger = None
            else:

                self._times = self._times + 1
                last_trigger = yield from self._motion_sensor.latest_trigger()
        except Exception:
            last_trigger = None
            _LOGGER.exception('failed to update motion sensor')

        if not last_trigger:
            return

        has_timed_out = (datetime.now() - last_trigger).seconds > self._timeout
        if has_timed_out:
            if self._on:
                self._on = False
                self.hass.async_add_job(self.async_update_ha_state(True))
        else:
            if not self._on:
                self._on = True
                self.hass.async_add_job(self.async_update_ha_state(True))
