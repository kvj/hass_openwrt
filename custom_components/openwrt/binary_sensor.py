from homeassistant.config_entries import ConfigEntry
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant

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

    # This one will be always here
    entities.append(OpenWrtSensor(device, device_id))

    for net_id in device.coordinator.data["mwan3"]:
        entities.append(
            Mwan3OnlineBinarySensor(device, device_id, net_id)
        )
    async_add_entities(entities)
    return True


class OpenWrtSensor(OpenWrtEntity, BinarySensorEntity):

    def __init__(self, device, device_id: str):
        super().__init__(device, device_id)

    @property
    def is_on(self):
        return True

    @property
    def device_class(self):
        return "connectivity"


class Mwan3OnlineBinarySensor(OpenWrtEntity, BinarySensorEntity):

    def __init__(self, device, device_id: str, interface: str):
        super().__init__(device, device_id)
        self._interface_id = interface

    @property
    def available(self):
        return self._interface_id in self.data["mwan3"]

    @property
    def unique_id(self):
        return "%s.%s.mwan3_online" % (super().unique_id, self._interface_id)

    @property
    def name(self):
        return f"{super().name} Mwan3 [{self._interface_id}] online"

    @property
    def is_on(self):
        data = self.data["mwan3"].get(self._interface_id, {})
        return data.get("online", False)

    @property
    def device_class(self):
        return "connectivity"

    @property
    def icon(self):
        return "mdi:access-point-network" if self.is_on else "mdi:access-point-network-off"
