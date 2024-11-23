from unittest import result
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util.json import json_loads

from .ubus import Ubus
from .constants import DOMAIN

import logging
from datetime import timedelta

_LOGGER = logging.getLogger(__name__)


class DeviceCoordinator:

    def __init__(self, hass, config: dict, ubus: Ubus, all_devices: dict):
        self._config = config
        self._ubus = ubus
        self._all_devices = all_devices
        self._id = config["id"]
        self._apis = None
        self._wps = config.get("wps", False)

        self._coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name='openwrt',
            update_method=self.make_async_update_data(),
            update_interval=timedelta(seconds=config.get("interval", 30))
        )

    @property
    def coordinator(self) -> DataUpdateCoordinator:
        return self._coordinator

    def _configured_devices(self, config_name):
        value = self._config.get(config_name, "")
        if value == "":
            return []
        return list([x.strip() for x in value.split(",")])

    async def discover_devices(self) -> dict:
        result = dict()

        if self.is_api_supported("network.device"):
            try:
                response = await self._ubus.api_call('network.device', 'status', {})
                _LOGGER.debug(f"Device status response: {response}")
                for device in response.get('devices', []):
                    if 'mac' in device:
                        result[device['mac']] = {
                            'hostname': device.get('hostname', ''),
                            'ip': device.get('ip', ''),
                            'mac': device['mac'],
                            'type': 'lan',
                        }
            except Exception as err:
                _LOGGER.warning(f"Error discovering LAN devices: {err}")

        if self.is_api_supported("network.wireless"):
            try:
                response = await self._ubus.api_call('network.wireless', 'status', {})
                _LOGGER.debug(f"Wireless status response: {response}")
                for radio, item in response.items():
                    if item.get('disabled', False):
                        continue
                    for iface in item['interfaces']:
                        if 'ifname' not in iface:
                            continue
                        for client in iface.get('clients', []):
                            if 'mac' in client:
                                result[client['mac']] = {
                                    'hostname': client.get('hostname', ''),
                                    'ip': client.get('ip', ''),
                                    'mac': client['mac'],
                                    'type': 'wifi',
                                }
            except Exception as err:
                _LOGGER.warning(f"Error discovering WLAN devices: {err}")

        if self.is_api_supported("mwan3"):
            try:
                response = await self._ubus.api_call('mwan3', 'status', {})
                for iface in response.get('interfaces', {}).values():
                    if iface.get("status") == "online":
                        result[iface['mac']] = {
                            'hostname': iface.get('hostname', ''),
                            'ip': iface.get('ip', ''),
                            'mac': iface['mac'],
                            'type': 'wan',
                        }
            except Exception as err:
                _LOGGER.warning(f"Error discovering WAN devices: {err}")

        return result

    async def discover_wireless(self) -> dict:
        result = dict(ap=[], mesh=[])
        if not self.is_api_supported("network.wireless"):
            return result
        wifi_devices = self._configured_devices("wifi_devices")
        try:
            response = await self._ubus.api_call('network.wireless', 'status', {})
            _LOGGER.debug(f"Wireless status response: {response}")
            for radio, item in response.items():
                if item.get('disabled', False):
                    continue
                for iface in item['interfaces']:
                    if 'ifname' not in iface:
                        continue
                    conf = dict(ifname=iface['ifname'],
                                network=iface['config']['network'][0])
                    if iface['config']['mode'] == 'ap':
                        if len(wifi_devices) and iface['ifname'] not in wifi_devices:
                            continue
                        result['ap'].append(conf)
                    if iface['config']['mode'] == 'mesh':
                        conf['mesh_id'] = iface['config']['mesh_id']
                        result['mesh'].append(conf)
        except NameError as err:
            _LOGGER.warning(f"Device [{self._id}] doesn't support wireless: {err}")
        return result

    def find_mesh_peers(self, mesh_id: str):
        result = []
        for _, device in self._all_devices.items():
            data = device.coordinator.data
            if not data or 'mesh' not in data or not data['mesh']:
                _LOGGER.warning(f"Missing or invalid 'mesh' data for device: {device}")
                continue
            for _, mesh in data['mesh'].items():
                if mesh['id'] == mesh_id:
                    result.append(mesh['mac'])
        return result

    async def update_mesh(self, configs) -> dict:
        mesh_devices = self._configured_devices("mesh_devices")
        result = dict()
        if not self.is_api_supported("iwinfo"):
            return result
        try:
            for conf in configs:
                if len(mesh_devices) and conf['ifname'] not in mesh_devices:
                    continue
                info = await self._ubus.api_call(
                    'iwinfo',
                    'info',
                    dict(device=conf['ifname'])
                )
                peers = {}
                result[conf['ifname']] = dict(
                    mac=info['bssid'].lower(),
                    signal=info.get("signal", -100),
                    id=conf['mesh_id'],
                    noise=info.get("noise", 0),
                    bitrate=info.get("bitrate", -1),
                    peers=peers,
                )
                for mac in self.find_mesh_peers(conf['mesh_id']):
                    try:
                        assoc = await self._ubus.api_call(
                            'iwinfo',
                            'assoclist',
                            dict(device=conf['ifname'], mac=mac)
                        )
                        peers[mac] = dict(
                            active=assoc.get("mesh plink") == "ESTAB",
                            signal=assoc.get("signal", -100),
                            noise=assoc.get("noise", 0)
                        )
                    except ConnectionError:
                        _LOGGER.warning(f"Failed to get assoclist for {mac} on device {conf['ifname']}")
                        pass
        except ConnectionError as err:
            _LOGGER.warning(f"Device [{self._id}] doesn't support iwinfo: {err}")
        return result

    async def update_hostapd_clients(self, interface_id: str) -> dict:
        try:
            _LOGGER.debug(f"Updating hostapd clients for interface: {interface_id}")
            response = await self._ubus.api_call(
                f"hostapd.{interface_id}",
                'get_clients',
                dict()
            )
            _LOGGER.debug(f"Hostapd clients response for {interface_id}: {response}")

            if 'clients' in response:
                clients = response['clients']
            else:
                _LOGGER.warning(f"'clients' key not found in response for interface {interface_id}. Response: {response}")
                clients = {}

            macs = dict()
            for key, value in clients.items():
                macs[key] = dict(signal=value.get("signal"))

            result = dict(
                clients=len(macs),
                macs=macs,
            )

            if self._wps:
                try:
                    response = await self._ubus.api_call(
                        f"hostapd.{interface_id}",
                        'wps_status',
                        dict()
                    )
                    result["wps"] = response.get("pbc_status") == "Active"
                except ConnectionError:
                    _LOGGER.warning(f"Interface [{interface_id}] doesn't support WPS: {err}")

            return result

        except NameError as e:
            _LOGGER.warning(f"Could not find object for interface {interface_id}: {e}")
            return {}
        except Exception as e:
            _LOGGER.error(f"Error while updating hostapd clients for {interface_id}: {e}")
            return {}

    async def set_wps(self, interface_id: str, enable: bool):
        await self._ubus.api_call(
            f"hostapd.{interface_id}",
            "wps_start" if enable else "wps_cancel",
            dict()
        )
        await self.coordinator.async_request_refresh()

    async def do_reboot(self):
        _LOGGER.debug(f"Rebooting device: {self._id}")
        await self._ubus.api_call(
            "system",
            "reboot",
            dict()
        )

    async def do_file_exec(self, command: str, params, env: dict, extra: dict):
        _LOGGER.debug(f"Executing command: {self._id}: {command} with {params} env={env}")
        result = await self._ubus.api_call(
            "file",
            "exec",
            dict(command=command, params=params, env=env) if len(env) else dict(command=command, params=params)
        )
        _LOGGER.debug(f"Execute result: {self._id}: {result}")
        self._coordinator.hass.bus.async_fire(
            "openwrt_exec_result",
            {
                "address": self._config.get("address"),
                "id": self._config.get("id"),
                "command": command,
                "code": result.get("code", 1),
                "stdout": result.get("stdout", ""),
                **extra,
            },
        )

        def process_output(data: str):
            try:
                json = json_loads(data)
                if isinstance(json, (list, dict)):
                    return json
            except Exception as e:
                _LOGGER.debug(f"Failed to parse JSON output: {e}")
                pass
            return data.strip().split("\n")

        return {
            "code": result.get("code", 1),
            "stdout": process_output(result.get("stdout", "")),
            "stderr": process_output(result.get("stderr", "")),
        }

    async def do_ubus_call(self, subsystem: str, method: str, params: dict):
        _LOGGER.debug(f"do_ubus_call(): {subsystem} / {method}: {params}")
        return await self._ubus.api_call(subsystem, method, params)

    async def do_rc_init(self, name: str, action: str):
        _LOGGER.debug(f"Executing name: {self._id}: {name} with {action}")
        result = await self._ubus.api_call(
            "rc",
            "init",
            dict(name=name, action=action)
        )
        _LOGGER.debug(f"Execute result: {self._id}: {result}")
        self._coordinator.hass.bus.async_fire(
            "openwrt_init_result",
            {
                "address": self._config.get("address"),
                "id": self._config.get("id"),
                "name": name,
                "code": result.get("code", 1),
                "stdout": result.get("stdout", ""),
            },
        )

    async def update_ap(self, configs) -> dict:
        result = dict()
        for item in configs:
            if 'ifname' in item:
                ifname = item['ifname']
                try:
                    _LOGGER.debug(f"Updating AP for interface: {ifname}")
                    result[ifname] = await self.update_hostapd_clients(ifname)
                except Exception as e:
                    _LOGGER.error(f"Error updating AP for {ifname}: {e}")
                    continue  # Continue with the next item
            else:
                _LOGGER.warning(f"Missing 'ifname' in AP config: {item}")
        return result

    async def update_info(self) -> dict:
        result = dict()
        response = await self._ubus.api_call("system", "board", {})
        return {
            "model": response["model"],
            "manufacturer": response["release"]["distribution"],
            "sw_version": "%s %s" % (
                response["release"]["version"],
                response["release"]["revision"]
            ),
        }

    async def discover_mwan3(self):
        if not self.is_api_supported("mwan3"):
            return dict()
        result = dict()
        response = await self._ubus.api_call(
            "mwan3",
            "status",
            dict(section="interfaces")
        )
        for key, iface in response.get("interfaces", {}).items():
            if not iface.get("enabled", False):
                continue
            result[key] = {
                "offline_sec": iface.get("offline", 0),
                "online_sec": iface.get("online", 0),
                "uptime_sec": iface.get("uptime", 0),
                "online": iface.get("status") == "online",
                "status": iface.get("status"),
                "up": iface.get("up")
            }
        return result

    async def update_wan_info(self):
        result = dict()
        devices = self._configured_devices("wan_devices")
        for device_id in devices:
            response = await self._ubus.api_call(
                "network.device",
                "status",
                dict(name=device_id)
            )
            stats = response.get("statistics", {})
            _LOGGER.debug("WAN: %s", response)
            result[device_id] = {
                "up": response.get("up", False),
                "rx_bytes": stats.get("rx_bytes", 0),
                "tx_bytes": stats.get("tx_bytes", 0),
                "speed": response.get("speed"),
                "mac": response.get("macaddr"),
            }
        return result

    async def load_ubus(self):
        return await self._ubus.api_list()

    def is_api_supported(self, name: str) -> bool:
        if self._apis and name in self._apis:
            return True
        return False

    def make_async_update_data(self):
        async def async_update_data():
            try:
                if not self._apis:
                    self._apis = await self.load_ubus()
                result = dict()
                result["info"] = await self.update_info()
                wireless_config = await self.discover_wireless()
                result['wireless'] = await self.update_ap(wireless_config['ap'])
                result['mesh'] = await self.update_mesh(wireless_config['mesh'])
                result["mwan3"] = await self.discover_mwan3()
                result["wan"] = await self.update_wan_info()
                devices = await self.discover_devices()
                _LOGGER.debug(f"Full update [{self._id}]: {result}")
                return result
            except PermissionError as err:
                raise ConfigEntryAuthFailed from err
            except Exception as err:
                _LOGGER.exception(f"Device [{self._id}] async_update_data error: {err}")
                raise UpdateFailed(f"OpenWrt communication error: {err}")
        return async_update_data

def new_ubus_client(hass, config: dict) -> Ubus:
    _LOGGER.debug(f"new_ubus_client(): {config}")
    schema = "https" if config["https"] else "http"
    port = ":%d" % (config["port"]) if config["port"] > 0 else ''
    url = "%s://%s%s%s" % (schema, config["address"], port, config["path"])
    return Ubus(
        hass.async_add_executor_job,
        url,
        config["username"],
        config.get("password", ""),
        verify=config.get("verify_cert", True)
    )

def new_coordinator(hass, config: dict, all_devices: dict) -> DeviceCoordinator:
    _LOGGER.debug(f"new_coordinator: {config}, {all_devices}")
    connection = new_ubus_client(hass, config)
    device = DeviceCoordinator(hass, config, connection, all_devices)
    return device
