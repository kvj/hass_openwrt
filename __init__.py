from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers import device_registry
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
import logging

from .coordinator import new_coordinator

_LOGGER = logging.getLogger(__name__)

from .constants import DOMAIN, PLATFORMS

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
    }),
}, extra=vol.ALLOW_EXTRA)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    data = entry.as_dict()['data']

    device = new_coordinator(hass, data, hass.data[DOMAIN]['devices'])

    await device.coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN]['devices'][entry.entry_id] = device
    for p in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, p)
        )
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    for p in PLATFORMS:
        await hass.config_entries.async_forward_entry_unload(entry, p)
    hass.data[DOMAIN]['devices'].pop(entry.entry_id)
    return True

async def async_reboot_device(hass: HomeAssistant, devices: dict, device_id: str):
    registry = device_registry.async_get(hass)
    device_entry = registry.async_get(device_id)
    if not device_entry:
        raise HomeAssistantError(f"Device {device_id} not found")
    for entry in device_entry.config_entries:
        device = devices.get(entry)
        if device:
            await device.do_reboot()
            _LOGGER.info(f"Reboot successful: {entry}")
            return True
    raise HomeAssistantError(f"OpenWrt device wasn't found: {device_id}")

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    hass.data[DOMAIN] = dict(devices={})

    async def async_reboot(call):
        _LOGGER.debug(f"async_reboot: {call.data}")
        if "device_id" not in call.data:
            raise HomeAssistantError("Device (device_id) is expected")
        for device_id in call.data["device_id"]:
            await async_reboot_device(hass, hass.data[DOMAIN]["devices"], device_id)
        return True

    hass.services.async_register(DOMAIN, "reboot", async_reboot)

    return True

class OpenWrtEntity(CoordinatorEntity):
    def __init__(self, device, device_id: str):
        super().__init__(device.coordinator)
        self._device_id = device_id
        self._device = device

    @property
    def device_info(self):
        return {
            "identifiers": {
                ("id", self._device_id)
            },
            "name": f"OpenWrt [{self._device_id}]",
            "model": self.data["info"]["model"],
            "manufacturer": self.data["info"]["manufacturer"],
            "sw_version": self.data["info"]["sw_version"],
        }

    @property
    def name(self):
        return "OpenWrt [%s]" % (self._device_id)

    @property
    def unique_id(self):
        return "sensor.openwrt.%s" % (self._device_id)

    @property
    def data(self) -> dict:
        return self.coordinator.data
