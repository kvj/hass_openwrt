from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.components.sensor import SensorEntity
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

    wireless = []
    for net_id in device.coordinator.data['wireless']:
        sensor = WirelessClientsSensor(device, device_id, net_id)
        wireless.append(sensor)
        entities.append(sensor)
    if len(wireless) > 0:
        entities.append(WirelessTotalClientsSensor(
            device, device_id, wireless))
    for net_id in device.coordinator.data['mesh']:
        entities.append(
            MeshSignalSensor(device, device_id, net_id)
        )
        entities.append(
            MeshPeersSensor(device, device_id, net_id)
        )
    for net_id in device.coordinator.data["mwan3"]:
        entities.append(
            Mwan3OnlineSensor(device, device_id, net_id)
        )
    async_add_entities(entities)
    return True


class OpenWrtSensor(OpenWrtEntity, SensorEntity):
    def __init__(self, coordinator, device: str):
        super().__init__(coordinator, device)

    @property
    def state_class(self):
        return 'measurement'


class WirelessClientsSensor(OpenWrtSensor):

    def __init__(self, device, device_id: str, interface: str):
        super().__init__(device, device_id)
        self._interface_id = interface

    @property
    def unique_id(self):
        return "%s.%s.clients" % (super().unique_id, self._interface_id)

    @property
    def name(self):
        return "%s Wireless [%s] clients" % (super().name, self._interface_id)

    @property
    def state(self):
        return self.data['wireless'][self._interface_id]['clients']

    @property
    def icon(self):
        return 'mdi:wifi-off' if self.state == 0 else 'mdi:wifi'

    @property
    def extra_state_attributes(self):
        result = dict()
        data = self.data['wireless'][self._interface_id]
        for key, value in data.get("macs", {}).items():
            signal = value.get("signal", 0)
            result[key.upper()] = f"{signal} dBm"
        return result


class MeshSignalSensor(OpenWrtSensor):

    def __init__(self, device, device_id: str, interface: str):
        super().__init__(device, device_id)
        self._interface_id = interface

    @property
    def unique_id(self):
        return "%s.%s.mesh_signal" % (super().unique_id, self._interface_id)

    @property
    def name(self):
        return f"{super().name} Mesh [{self._interface_id}] signal"

    @property
    def state(self):
        value = self.data['mesh'][self._interface_id]['signal']
        return f"{value} dBm"

    @property
    def device_class(self):
        return 'signal_strength'

    @property
    def signal_strength(self):
        value = self.data['mesh'][self._interface_id]['signal']
        levels = [-50, -60, -67, -70, -80]
        for idx, level in enumerate(levels):
            if value >= level:
                return idx
        return len(levels)

    @property
    def icon(self):
        icons = ['mdi:network-strength-4', 'mdi:network-strength-3', 'mdi:network-strength-2',
                 'mdi:network-strength-1', 'mdi:network-strength-outline', 'mdi:network-strength-off-outline']
        return icons[self.signal_strength]


class MeshPeersSensor(OpenWrtSensor):

    def __init__(self, device, device_id: str, interface: str):
        super().__init__(device, device_id)
        self._interface_id = interface

    @property
    def unique_id(self):
        return "%s.%s.mesh_peers" % (super().unique_id, self._interface_id)

    @property
    def name(self):
        return f"{super().name} Mesh [{self._interface_id}] peers"

    @property
    def state(self):
        peers = self.data["mesh"][self._interface_id]["peers"]
        return len(list(filter(lambda x: x["active"], peers.values())))

    @property
    def icon(self):
        return 'mdi:server-network' if self.state > 0 else 'mdi:server-network-off'

    @property
    def extra_state_attributes(self):
        result = dict()
        data = self.data["mesh"][self._interface_id]
        for key, value in data.get("peers", {}).items():
            signal = value.get("signal", 0)
            result[key.upper()] = f"{signal} dBm"
        return result


class WirelessTotalClientsSensor(OpenWrtSensor):

    def __init__(self, device, device_id: str, sensors):
        super().__init__(device, device_id)
        self._sensors = sensors

    @property
    def unique_id(self):
        return "%s.total_clients" % (super().unique_id)

    @property
    def name(self):
        return "%s Wireless total clients" % (super().name)

    @property
    def state(self):
        total = 0
        for item in self._sensors:
            total += item.state
        return total

    @property
    def icon(self):
        return 'mdi:wifi-off' if self.state == 0 else 'mdi:wifi'


class Mwan3OnlineSensor(OpenWrtSensor):

    def __init__(self, device, device_id: str, interface: str):
        super().__init__(device, device_id)
        self._interface_id = interface

    @property
    def unique_id(self):
        return "%s.%s.mwan3_online_ratio" % (super().unique_id, self._interface_id)

    @property
    def name(self):
        return f"{super().name} Mwan3 [{self._interface_id}] online ratio"

    @property
    def state(self):
        data = self.data["mwan3"][self._interface_id]
        value = data["online_sec"] / data["uptime_sec"] * \
            100 if data["uptime_sec"] else 100
        return f"{round(value, 1)}%"

    @property
    def icon(self):
        return "mdi:router-network"
