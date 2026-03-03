import sys
import os

# Add project root to sys.path
sys.path.append("/opt/JSBach_V4.2")

from app.modules.wifi.wifi import config
import json

CONFIG_FILE = "/opt/JSBach_V4.2/config/wifi/wifi.json"

# Test config with interface
params = {
    "ssid": "JSBach_Home_AP",
    "password": "jsbach_ultra_secure_2026",
    "channel": 11,
    "ip_address": "10.0.99.1",
    "netmask": "255.255.255.0",
    "dhcp_start": "10.0.99.100",
    "dhcp_end": "10.0.99.200",
    "interface": "wlan0"
}

success, msg = config(params)
print(f"Success: {success}, Message: {msg}")

if success:
    with open(CONFIG_FILE, "r") as f:
        cfg = json.load(f)
        print(f"Updated Interface: {cfg.get('interface')}")
