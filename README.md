## Home Assistant integration with OpenWrt devices

### Features:
* Sensors:
  * Wireless clients counters
  * Number of connected mesh peers
  * Signal strength of mesh links
  * `mwan3` interface online ratio
  * WAN interfaces Rx&Tx bytes counters (if configured)
* Switches:
  * Control WPS status
* Binary sensors:
  * `mwan3` connectivity status
* Services:
  * Reboot device: `openwrt.reboot`
  * Execute arbitrary command: `openwrt.exec` (see the configuration below) 

### Installing
* OpeWrt device(s):
  * Make sure that `uhttpd uhttpd-mod-ubus rpcd` packages are installed (if you use custom images)
    * If you use mesh networks, install `rpcd-mod-iwinfo` package
  * Make sure that `ubus` is available via http using the manual: https://openwrt.org/docs/techref/ubus
    * To make it right, please refer to the `Ubus configuration` section below

* Home Assistant:
  * Add this repo as a custom integration using HACS
  * Restart server
  * Go to `Integrations` and add a new `OpenWrt` integration

### Ubus configuration
* Create new file `/usr/share/rpcd/acl.d/hass.json`:
```json
{
  "hass": {
    "description": "Home Assistant OpenWrt integraion permissions",
    "read": {
      "ubus": {
        "network.wireless": ["status"],
        "network.device": ["status"],
        "iwinfo": ["info", "assoclist"],
        "hostapd.*": ["get_clients", "wps_status"],
        "system": ["board"],
        "mwan3": ["status"]
      },
    },
    "write": {
      "ubus": {
        "system": ["reboot"],
        "hostapd.*": ["wps_start", "wps_cancel"]
      }
    }
  }
}

```
* Add new system user `hass` (or do it in any other way that you prefer):
  * Add line to `/etc/passwd`: `hass:x:10001:10001:hass:/var:/bin/false`
  * Add line to `/etc/shadow`: `hass:x:0:0:99999:7:::`
  * Change password: `passwd hass`
* Edit `/etc/config/rpcd` and add:
```
config login
        option username 'hass'
        option password '$p$hass'
        list read hass
        list read unauthenticated
        list write hass
```
* Restart rpcd: `/etc/init.d/rpcd restart`

### Executing command

In order to allow ubus/rpcd execute a command remotely, the command should be added to the permissions ACL file above. The extra configuration could look like below (gives permission to execute `uptime` command):
```json
{
  "hass": {
    "write": {
      "ubus": {
        /* ... */
        "file": ["exec"]
      },
      "file": {
        /* ... */
        "/usr/bin/uptime": ["exec"]
      }
    },
  }
}
```

### Screenshots:

<img width="1050" alt="Screenshot 2021-10-11 at 14 07 34" src="https://user-images.githubusercontent.com/159124/136787603-04d3f48f-5726-45ab-94f1-c3c3b8b39c53.png">

<img width="554" alt="Screenshot 2021-10-11 at 14 08 15" src="https://user-images.githubusercontent.com/159124/136787627-01e527a7-cf7f-4527-8330-8aa68f22d13e.png">
