import os
import sys
import subprocess
import time
import json
import logging

BASE_DIR = "/opt/JSBach_V4.2"
sys.path.append(BASE_DIR)

# Configure minimal logging for stdout
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s', stream=sys.stdout)
logger = logging.getLogger(__name__)

import builtins

original_open = builtins.open

def mocked_open(*args, **kwargs):
    filename = args[0]
    if isinstance(filename, str) and "/opt/JSBach_V4.2/logs/" in filename:
        filename = filename.replace("/opt/JSBach_V4.2/logs/", "/tmp/jsbach_logs/")
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        args_list = list(args)
        args_list[0] = filename
        args = tuple(args_list)
    return original_open(*args, **kwargs)

builtins.open = mocked_open

from app.modules.firewall import firewall
from app.modules.dhcp import dhcp
from app.modules.ebtables import ebtables
import app.modules.wifi.wifi as wifi
from app.utils.global_helpers import module_helpers as mh
from app.utils.global_helpers import io_helpers as ioh

# Ensure no other log errors
def dummy_log(*args, **kwargs):
    pass
ioh.log_action = dummy_log

def run_cmd(cmd):
    try:
        res = subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return res.stdout
    except subprocess.CalledProcessError as e:
        return e.stdout + "\n" + e.stderr

def log_header(title):
    print(f"\n{'='*50}")
    print(f"[{time.strftime('%H:%M:%S')}] {title}")
    print(f"{'='*50}\n")

def check_iptables(table="filter", grep_term=None):
    cmd = f"sudo iptables -t {table} -S"
    out = run_cmd(cmd)
    if grep_term:
        return "\n".join([line for line in out.splitlines() if grep_term in line])
    return out

def check_ebtables(grep_term=None):
    cmd = f"sudo ebtables -L"
    out = run_cmd(cmd)
    if grep_term:
         return "\n".join([line for line in out.splitlines() if grep_term in line])
    return out

def run_tests():
    # TEST 1: STOP EVERYTHING
    log_header("TEST 1: INITIALIZING SYSTEM STAGE (STOPPING ALL)")
    wifi.stop()
    dhcp.stop()
    ebtables.stop()
    firewall.stop()
    
    print("Checking iptables should be mostly clean...")
    print(check_iptables(grep_term="WIFI"))
    print("Checking ebtables should be clean...")
    print(check_ebtables())
    
    # TEST 2: START BASE MODULES (VLANs, FIREWALL, DHCP)
    log_header("TEST 2: START CORE MODULES (FW, DHCP, EBTABLES)")
    # En JSBach el orden normal de arranque suele ser Ebtables -> Firewall -> DHCP
    print("Starting ebtables...")
    ebtables.start()
    print("Starting firewall...")
    firewall.start()
    print("Starting dhcp...")
    dhcp.start()
    
    time.sleep(2)
    print("Core modules started. Checking ebtables for VLAN rules:")
    print(check_ebtables("vlan"))
    print("\nChecking iptables for VLAN INPUT rules:")
    print(check_iptables("filter", "INPUT_VLAN"))
    
    # TEST 3: START WIFI (INTEGRATION TEST)
    log_header("TEST 3: START WIFI (INTEGRATION)")
    print("Starting wifi module...")
    wifi.start()
    time.sleep(3)
    
    print("\n[VERIFICATION A] DHCP config for Wi-Fi interface exist:")
    print(run_cmd("cat /etc/dnsmasq.d/wlp3s0.conf || echo 'Not found'"))
    
    print("\n[VERIFICATION B] Ebtables Wi-Fi Integration (Isolation/Blacklist):")
    print(check_ebtables("wlp3s0"))
    
    print("\n[VERIFICATION C] Iptables Wi-Fi Captive Portal Rules:")
    print(check_iptables("mangle", "wlp3s0"))
    print(check_iptables("nat", "wlp3s0"))
    
    print("\n[VERIFICATION D] Iptables Wi-Fi Base Security Rules (INPUT/FORWARD):")
    print(check_iptables("filter", "WIFI"))
    
    # TEST 4: WIFI STOP GRACEFULLY RETURNS TO NORMAL
    log_header("TEST 4: STOP WIFI REVERTS CHANGES")
    print("Stopping Wi-Fi...")
    wifi.stop()
    time.sleep(2)
    
    print("\nVerify Ebtables has removed Wi-Fi references but kept VLANs:")
    print(check_ebtables("vlan")) # Should still be there
    print(check_ebtables("wlp3s0")) # Should be empty
    
    print("\nVerify Iptables has removed Wi-Fi references but kept VLANs:")
    print(check_iptables("filter", "INPUT_VLAN")) # Should still be there
    print(check_iptables("filter", "WIFI")) # Should be empty
    print(check_iptables("nat", "PORTAL_CAPTIVO")) # Should be empty or clean
    
    # TEST 6: REVERSE INITIALIZATION (WIFI FIRST, THEN CORE)
    log_header("TEST 6: REVERSE INITIALIZATION (WIFI FIRST)")
    print("Stopping all again...")
    ebtables.stop()
    firewall.stop()
    dhcp.stop()
    wifi.stop()
    time.sleep(2)
    
    print("Starting Wi-Fi first...")
    wifi.start()
    time.sleep(3)
    
    print("Captive Portal rules after Wi-Fi start (expected: ONLY portal rules because core FW is off or flushed):")
    print(check_iptables("mangle", "wlp3s0"))
    
    print("\nStarting Core Modules (Ebtables, Firewall, DHCP)...")
    ebtables.start()
    firewall.start()
    dhcp.start()
    time.sleep(2)
    
    print("\nCaptive Portal rules after Core start (Did the firewall flush kill our portal? JSBach firewall.start() flushes iptables!):")
    print(check_iptables("mangle", "wlp3s0"))
    print("\nWARNING: If the above is empty, it proves an architectural design in JSBach where the global Firewall has authority and erases external rules. To fix it, you'd just need to ensure `wifi.start()` or `wifi` reload is called after `firewall` reboots.")
    
    # Let's fix it by "reloading" wifi if it was running, just by calling start again, which is safe
    print("Calling wifi.start() to simulate self-healing or re-assertion of rules:")
    wifi.start()
    print(check_iptables("mangle", "wlp3s0"))
    
    
    # TEST 7: MAC RESTRICTION ON VLAN WHILE WIFI IS RUNNING
    log_header("TEST 7: MODIFICAR VLAN MAC FILTER MIENTRAS WIFI CORRE")
    print("Añadiendo una regla de Blacklist a VLAN 1 (simulado en Firewall API)")
    # We will simulate applying an isolation/whitelist function on firewall for a VLAN
    firewall.enable_whitelist({"vlan_id": 1})
    time.sleep(1)
    
    print("\nReglas de Ebtables después de aislar VLAN 1 (Asegurar que las de Wi-Fi siguen arriba):")
    print(check_ebtables())
    
    
    # TEST 8: STOPPING CORE WHILE WIFI IS RUNNING
    log_header("TEST 8: STOPPING CORE, KEEPING WIFI")
    print("Stopping Core modules...")
    firewall.stop()
    ebtables.stop()
    dhcp.stop()
    time.sleep(2)
    
    print("\nChecking if Wi-Fi rules survived Core stop (Spoiler: firewall.stop() issues iptables -F):")
    print(check_iptables("mangle", "wlp3s0"))
    print(check_iptables("filter", "WIFI"))
    print(check_ebtables("wlp3s0")) # If ebtables.stop() runs ebtables -t filter -F, it kills Wi-Fi capado too.
    
    
    # TEST 9: WIFI MAC BLACKLIST VERIFICATION
    log_header("TEST 9: WIFI MAC BLACKLIST VERIFICATION (CAPA 2)")
    print("Reiniciando sistema base normal para la última prueba...")
    ebtables.start()
    firewall.start()
    dhcp.start()
    wifi.start()
    time.sleep(2)
    
    print("Configurando un MAC Blacklist en el WiFi (AA:BB:CC:DD:EE:FF)...")
    # API simulation
    ebtables.enable_blacklist({"vlan_id": "wifi"})
    time.sleep(1)
    ebtables.add_mac({"vlan_id": "wifi", "mac": "AA:BB:CC:DD:EE:FF"})
    time.sleep(1)
    
    print("\nVerificando que la regla MAC aparezca al PRINCIPIO de Ebtables (antes del enrutamiento de red normal):")
    print(check_ebtables("AA:BB:CC:DD:EE:FF"))
    
    # Remove it for cleanup
    ebtables.remove_mac({"vlan_id": "wifi", "mac": "AA:BB:CC:DD:EE:FF"})
    ebtables.disable_blacklist({"vlan_id": "wifi"})

    # TEST 10: FINAL CLEANUP
    log_header("TEST 10: BRING EVERYTHING BACK ONLINE")
    print("Starting full system normally based on user config...")
    wifi.start()
    
    print("\nTests complete. Review stdout for conflicts.")

if __name__ == '__main__':
    run_tests()
