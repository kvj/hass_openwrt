from homeassistant.config_entries import ConfigEntry
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

import logging

from . import OpenWrtEntity
from .constants import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities
) -> None:
    entities = []
    data = entry.as_dict()
    device = hass.data[DOMAIN]['devices'][entry.entry_id]
    device_id = data['data']['id']
    for net_id, info in device.coordinator.data['wireless'].items():
        if "wps" in info:
            sensor = WirelessWpsSwitch(device, device_id, net_id)
            entities.append(sensor)
    async_add_entities(entities)
    return True


class WirelessWpsSwitch(OpenWrtEntity, SwitchEntity):
    def __init__(self, device, device_id, interface: str):
        super().__init__(device, device_id)
        self._interface_id = interface

    @property
    def unique_id(self):
        return "%s.%s.wps" % (super().unique_id, self._interface_id)

    @property
    def name(self):
        return "%s Wireless [%s] WPS toggle" % (super().name, self._interface_id)

    @property
    def is_on(self):
        return self.data["wireless"][self._interface_id]["wps"]

    async def async_turn_on(self, **kwargs):
        await self._device.set_wps(self._interface_id, True)
        self.data["wireless"][self._interface_id]["wps"] = True

    async def async_turn_off(self, **kwargs):
        await self._device.set_wps(self._interface_id, False)
        self.data["wireless"][self._interface_id]["wps"] = False

    @property
    def icon(self):
        return "mdi:security"

    @property
    def entity_category(self):
        return EntityCategory.CONFIG
