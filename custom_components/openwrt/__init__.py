from __future__ import annotations
from .constants import DOMAIN, PLATFORMS

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers import service
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
import logging

from .coordinator import new_coordinator

_LOGGER = logging.getLogger(__name__)


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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    hass.data[DOMAIN] = dict(devices={})

    async def async_reboot(call):
        for entry_id in await service.async_extract_config_entry_ids(hass, call):
            await hass.data[DOMAIN]["devices"][entry_id].do_reboot()

    async def async_exec(call):
        parts = call.data["command"].split(" ")
        for entry_id in await service.async_extract_config_entry_ids(hass, call):
            device = hass.data[DOMAIN]["devices"][entry_id]
            if device.is_api_supported("file"):
                await device.do_file_exec(
                    parts[0],
                    parts[1:],
                    call.data.get("environment", {})
                )

    hass.services.async_register(DOMAIN, "reboot", async_reboot)
    hass.services.async_register(DOMAIN, "exec", async_exec)

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
