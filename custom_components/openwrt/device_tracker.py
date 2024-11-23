from homeassistant.components.device_tracker import DeviceScanner, PLATFORM_SCHEMA
from homeassistant.helpers.entity import EntityCategory
from homeassistant.config_entries import ConfigEntry
from . import OpenWrtEntity
from .constants import DOMAIN

import logging

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass,
    entry: ConfigEntry,
    async_add_entities
) -> None:
    """Set up the OpenWrt device tracker."""
    entities = []
    data = entry.as_dict()
    device = hass.data[DOMAIN]['devices'][entry.entry_id]
    device_id = data['data']['id']

    # Stelle sicher, dass die Daten auf dem neuesten Stand sind
    await device.coordinator.async_refresh()  # Aktualisiere die Daten

    # Alle Geräte aus der discover_devices-Methode
    devices = device.coordinator.data.get('devices', {})

    for mac, device_info in devices.items():
        tracker = OpenWrtDeviceTracker(device, mac, device_info)
        entities.append(tracker)

    # Füge die Geräte-Tracker zu Home Assistant hinzu
    _LOGGER.debug(f"Found {len(entities)} device trackers to add.")
    async_add_entities(entities)

class OpenWrtDeviceTracker(OpenWrtEntity, DeviceScanner):
    """Device tracker for OpenWrt clients."""

    def __init__(self, coordinator, mac: str, device_info: dict):
        super().__init__(coordinator, device_info)
        self._mac = mac
        self._device_info = device_info
        self._state = None
        _LOGGER.debug(f"Initialized OpenWrtDeviceTracker for MAC {mac}")

    async def async_update(self):
        """Update the device tracker."""
        _LOGGER.debug(f"Updating device tracker for {self._mac}")
        # Fetch the latest device state
        self._state = await self._fetch_device_status()

    async def _fetch_device_status(self):
        """Fetch the current device status from the coordinator."""
        _LOGGER.debug(f"Fetching status for {self._mac}")
        if self._mac in self.coordinator.data['devices']:
            device_data = self.coordinator.data['devices'][self._mac]
            return device_data.get('status', 'not_home')
        return 'not_home'

    @property
    def name(self):
        """Return the name of the device tracker."""
        return f"Device Tracker {self._mac}"

    @property
    def state(self):
        """Return the state of the device tracker."""
        return self._state or 'not_home'

    @property
    def icon(self):
        """Return the icon for the device tracker."""
        return 'mdi:wifi' if self.state == 'home' else 'mdi:wifi-off'

    @property
    def extra_state_attributes(self):
        """Return extra state attributes for the device tracker."""
        return {
            "mac": self._mac,
            "hostname": self._device_info.get('hostname'),
            "type": self._device_info.get('type'),
        }
