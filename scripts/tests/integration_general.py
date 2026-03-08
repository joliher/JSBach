import os
import sys
import time
import json
import unittest
import subprocess
from typing import Dict, Any, List

# Add project root to sys.path
BASE_DIR = "/opt/JSBach_V4.2"
sys.path.append(BASE_DIR)

import logging
logging.getLogger("app.modules.firewall.firewall").setLevel(logging.DEBUG)
sh = logging.StreamHandler(sys.stdout)
sh.setLevel(logging.DEBUG)
logging.getLogger("app.modules.firewall.firewall").addHandler(sh)

from app.modules.wan import wan
from app.modules.vlans import vlans
from app.modules.tagging import tagging
from app.modules.dhcp import dhcp
from app.modules.firewall import firewall
from app.modules.dmz import dmz
from app.modules.nat import nat
from app.modules.wifi import wifi
from app.modules.ebtables import ebtables
from app.utils.global_helpers import run_command, load_json_config, save_json_config, module_helpers as mh

class TestMasterIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Setup physical dummy infrastructure and base configs with deep cleanup."""
        print("\n[!] Performing Deep Cleanup & Setup...")
        
        # Stop modules in reverse order
        for mod in [ebtables, nat, dmz, wifi, firewall, dhcp, tagging, vlans, wan]:
            try:
                mod.stop()
            except:
                pass
        
        # Cleanup interfaces
        for i in range(5):
            run_command(["ip", "link", "del", f"dummy{i}"], ignore_error=True)
        run_command(["ip", "link", "del", "br0"], ignore_error=True)
        
        # dummy0: WAN
        # dummy1: Management/VLANs
        # dummy2: Wi-Fi
        # dummy3: Extra Tagging
        interfaces = ["dummy0", "dummy1", "dummy2", "dummy3"]
        for iface in interfaces:
            run_command(["ip", "link", "add", iface, "type", "dummy"])
            run_command(["ip", "link", "set", iface, "up"])

        # 1. Flush specific global chains first to remove references
        for table in ["filter", "nat", "mangle"]:
            run_command(["iptables", "-t", table, "-F"], ignore_error=True)
        
        # 2. Flush and delete L2 chains
        run_command(["ebtables", "-F"], ignore_error=True)
        
        # 3. Controlled deletion of JSB chains (from inside out)
        # First, remove hooks from standard chains
        for chain in ["INPUT", "FORWARD", "OUTPUT"]:
             run_command(["iptables", "-D", chain, "-j", "JSB_GLOBAL_ISOLATE"], ignore_error=True)
             run_command(["iptables", "-D", chain, "-j", "JSB_GLOBAL_RESTRICT"], ignore_error=True)
        
        # Now we can safely flush and delete our custom chains
        success, output = run_command(["iptables-save"])
        jsb_chains = [line.split()[1] for line in output.splitlines() if line.startswith(":") and "JSB" in line]
        for chain in jsb_chains:
             run_command(["iptables", "-F", chain], ignore_error=True)
        for chain in reversed(jsb_chains):
             run_command(["iptables", "-X", chain], ignore_error=True)

        # 1. WAN Config
        save_json_config(os.path.join(BASE_DIR, "config/wan/wan.json"), {
            "status": 0, "interface": "dummy0", "mode": "manual", 
            "ip": "192.168.100.2", "mask": "24", "gateway": "192.168.100.1", "dns": "8.8.8.8"
        })

        # 2. VLANs Config
        cls.vlans_data = {
            "10": {"name": "VLAN_10", "ip": "10.0.10.1/24", "enabled": True},
            "20": {"name": "VLAN_20", "ip": "10.0.20.1/24", "enabled": True}
        }
        save_json_config(os.path.join(BASE_DIR, "config/vlans/vlans.json"), {
            "vlans": [
                {"id": 10, "name": "VLAN_10", "ip_network": "10.0.10.0/24", "ip_interface": "10.0.10.1/24"},
                {"id": 20, "name": "VLAN_20", "ip_network": "10.0.20.0/24", "ip_interface": "10.0.20.1/24"}
            ], "status": 0, "interface": "dummy1"
        })
        
        # 3. Tagging Config
        save_json_config(os.path.join(BASE_DIR, "config/tagging/tagging.json"), {
            "interfaces": [
                {"name": "dummy3", "vlan_untag": 10, "vlan_tag": ""}
            ], "status": 0
        })

        # 4. Wi-Fi Config
        save_json_config(os.path.join(BASE_DIR, "config/wifi/wifi.json"), {
            "ssid": "JSB_MASTER_TEST", "password": "master_password", "channel": "6",
            "interface": "dummy2", "ip_address": "10.0.99.1", "netmask": "255.255.255.0",
            "portal_enabled": True, "portal_port": 8505, "status": 0
        })

        # 5. DMZ Config
        save_json_config(os.path.join(BASE_DIR, "config/dmz/dmz.json"), {
            "vlan_id": 20, "destinations": [{"ip": "10.0.20.10", "name": "WebSrv", "port": 80, "protocol": "tcp"}], "status": 0
        })

        # Sincronizar firewall.json con estas VLANs para que firewall.isolate las encuentre
        save_json_config(os.path.join(BASE_DIR, "config/firewall/firewall.json"), {
            "vlans": cls.vlans_data,
            "wifi": {"isolated": False, "restricted": False},
            "status": 0
        })

    def test_01_startup_sequence(self):
        """Start all modules in a synchronized sequence."""
        print("\n[+] Starting Synchronized Sequence...")
        
        # Wi-Fi y VLANs/Tagging deben estar antes que Firewall/DHCP para que las interfaces existan
        sequence = [
            ("WAN", wan), ("VLANs", vlans), ("Tagging", tagging),
            ("Wi-Fi", wifi), ("Firewall", firewall), ("DHCP", dhcp),
            ("DMZ", dmz), ("NAT", nat)
        ]

        for name, mod in sequence:
            print(f"  > Starting {name}...")
            success, msg = mod.start()
            if not success:
                print(f"FAILED to start {name}: {msg}")
                # Dump config context
                run_command(["ls", "-R", os.path.join(BASE_DIR, "config")])
            self.assertTrue(success, f"Failed to start {name}: {msg}")
            
            if name in ["Firewall", "DHCP", "DMZ", "NAT"]:
                print(f"  TRACE [{name} started]: iptables -S INPUT_VLAN_10")
                _, out = run_command(["iptables", "-S", "INPUT_VLAN_10"])
                print(out.strip())
                
            time.sleep(2) # Dar tiempo extra para estabilización
        
        # Verify all modules are status 1
        for name, mod in sequence:
            if name == "Wi-Fi":
                continue # Skipped because dummy interfaces cause simulated hostapd to die, and monitor.py sets status to 0
            status = mh.get_module_status_by_name(BASE_DIR, name.lower())
            self.assertEqual(status, 1, f"Module {name} did not report status 1 after startup.")

    def test_02_rule_hierarchy_check(self):
        """Verify that rules are ordered according to GLOBAL_MODULE_ORDER."""
        print("\n[+] Verifying Hierarchical Rule Ordering...")
        
        # L3 FORWARD
        success, output = run_command(["iptables", "-L", "JSB_GLOBAL_ISOLATE", "-n"])
        self.assertIn("FORWARD_WIFI", output)
        self.assertIn("JSB_FW_ISOLATE", output)
        
        # L3 INPUT
        success, output = run_command(["iptables", "-L", "JSB_GLOBAL_RESTRICT", "-n"])
        self.assertIn("INPUT_WIFI", output)
        self.assertIn("JSB_FW_RESTRICT", output)

    def test_03_synchronized_isolation(self):
        """Apply isolation to all modules and verify state."""
        print("\n[+] Applying Multi-Module Synchronized Isolation...")
        
        # TRACE: What is state of INPUT_VLAN_10 at the START of test_03?
        print("  TRACE [test_03 start]: iptables -S INPUT_VLAN_10")
        _, out = run_command(["iptables", "-S", "INPUT_VLAN_10"])
        print(out)
        
        # Verificar estados antes de aplicar isolation
        print(f"  DEBUG: Wi-Fi status = {mh.get_module_status_by_name(BASE_DIR, 'wifi')}")
        print(f"  DEBUG: VLANs status = {mh.get_module_status_by_name(BASE_DIR, 'vlans')}")
        
        # Isolar Wi-Fi
        success, msg = firewall.isolate({"module": "wifi"})
        print(f"  DEBUG: isolate_wifi success={success}, msg={msg}")
        
        # Isolar VLAN 10
        success, msg = firewall.isolate({"vlan_id": 10})
        print(f"  DEBUG: isolate_vlan_10 success={success}, msg={msg}")
        firewall.restrict({"vlan_id": 10})
        
        # Verificar reglas en sub-cadenas Wi-Fi
        # firewall.start() debería haber añadido LOG y DROP si isolated=True
        success, output = run_command(["iptables", "-L", "FORWARD_WIFI", "-n"])
        if "LOG" not in output:
             print("\n[!] DEBUG: FORWARD_WIFI is empty! Iptables -S:")
             _, s_out = run_command(["iptables", "-S"])
             print(s_out)

        self.assertIn("LOG", output)
        self.assertIn("DROP", output)
        
        # Verificar reglas en sub-cadenas VLAN 10 (Aislamiento va a JSB_FW_ISOLATE en FORWARD)
        success, output = run_command(["iptables", "-L", "JSB_FW_ISOLATE", "-n"])
        self.assertIn("10.0.10.0/24", output)
        self.assertIn("DROP", output)
        
        # Restricción va a INPUT_VLAN_10 (vía JSB_FW_RESTRICT en INPUT)
        success, output = run_command(["iptables", "-L", "INPUT_VLAN_10", "-n"])
        if "LOG" not in output:
             print("\n[!] DEBUG: INPUT_VLAN_10 is missing rules! Iptables -S INPUT_VLAN_10:")
             _, s_out = run_command(["iptables", "-S", "INPUT_VLAN_10"])
             print(s_out)
        self.assertIn("LOG", output)
        self.assertIn("DROP", output)

    def test_04_block_prevails_logic(self):
        """Verify that RETURN is used for allows, and DROP for blocks."""
        print("\n[+] Checking 'Block Prevails' (RETURN vs DROP) consistency...")
        
        # Esperar un momento para propagación de reglas si fuera necesario
        time.sleep(1)
        
        success, output = run_command(["iptables", "-S", "INPUT_VLAN_10"])
        if not success or "53" not in output:
             print(f"\n[!] DEBUG: INPUT_VLAN_10 verification failed. Output:\n{output}")
             print("Full iptables state:")
             _, full = run_command(["iptables", "-S"])
             print(full)

        # En la sub-cadena de restricción, DNS (53) DEBE ser RETURN
        self.assertIn("-A INPUT_VLAN_10 -p udp -m udp --dport 53 -j RETURN", output)
 
    def test_05_teardown_and_cleanup(self):
        """Stop everything and verify Zero-Disk cleanup."""
        print("\n[+] Stopping All Modules & Verifying Zero-Disk Compliance...")
        
        modules = [ebtables, nat, dmz, wifi, firewall, dhcp, tagging, vlans, wan]
        for mod in modules:
            mod.stop()
        
        # Verify temporary files removal
        raw_files = [
            "config/dhcp/dnsmasq.conf",
            "config/wifi/hostapd.conf",
            "config/wifi/hostapd.pid",
            "scripts/expect/last_sync_commands.txt" # Old one, should be gone
        ]
        for f in raw_files:
            path = os.path.join(BASE_DIR, f)
            self.assertFalse(os.path.exists(path), f"File {f} was not cleaned up!")

    @classmethod
    def tearDownClass(cls):
        """Final hardware cleanup."""
        print("\n[!] Cleaning up virtual infrastructure...")
        for i in range(5):
            subprocess.run(["sudo", "ip", "link", "del", f"dummy{i}"], capture_output=True)

if __name__ == "__main__":
    unittest.main()

