# Home Assistant integration with OpenWrt devices

[![hacs_badge](https://img.shields.io/badge/HACS-custom-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)


## Features

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
* Device Tracker:
  * Display states of connected devices, based on the [official HA integration](https://www.home-assistant.io/integrations/ubus/)
* Services:
  * Reboot device: `openwrt.reboot`
  * Execute arbitrary command: `openwrt.exec` (see the configuration below)
  * Manage services using command-line: `openwrt.init` (see the configuration below)

### Installing

* OpenWrt device(s):
  * Make sure that `uhttpd uhttpd-mod-ubus rpcd` packages are installed (if you use custom images)
    * If you use mesh networks, install `rpcd-mod-iwinfo` package
  * Make sure that `ubus` is available via http using the manual: <https://openwrt.org/docs/techref/ubus>
    * To make it right, please refer to the `Ubus configuration` section below

* Home Assistant:
  * Add this repo as a custom integration using HACS
  * Restart server
  * Go to `Integrations` and add a new `OpenWrt` integration

### Ubus configuration

* Create new file `/usr/share/rpcd/acl.d/hass.json`:

```jsonc
{
  "hass": {
    "description": "Home Assistant OpenWrt integration permissions",
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

```jsonc
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

### Manage services using command-line

In order to allow ubus/rpcd execute a command remotely, the command should be added to the permissions ACL file above. The extra configuration could look like below (gives permission to manage `presence-detector` service. Start, stop, restart, enable and disable system services.):

```jsonc
{
  "hass": {
    "write": {
      "ubus": {
        /* ... */
        "rc": ["init"]
      },
      "rc": {
        /* ... */
        "/etc/init.d/presence-detector": ["init"]
      }
    },
  }
}
```

### Screenshots

<img width="1050" alt="Screenshot 2021-10-11 at 14 07 34" src="https://user-images.githubusercontent.com/159124/136787603-04d3f48f-5726-45ab-94f1-c3c3b8b39c53.png">

<img width="554" alt="Screenshot 2021-10-11 at 14 08 15" src="https://user-images.githubusercontent.com/159124/136787627-01e527a7-cf7f-4527-8330-8aa68f22d13e.png">
