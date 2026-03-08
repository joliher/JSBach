#!/usr/bin/env python3
import sys
import os
import asyncio
import shutil
import subprocess
import json

# Añadir el directorio raíz al path para importar módulos de JSBach
BASE_DIR = "/opt/JSBach_V4.2"
sys.path.append(BASE_DIR)

from app.modules.wan import wan
from app.modules.vlans import vlans

CONFIG_FILE_WAN = os.path.join(BASE_DIR, "config/wan/wan.json")
CONFIG_FILE_VLANS = os.path.join(BASE_DIR, "config/vlans/vlans.json")
BACKUP_FILE_WAN = CONFIG_FILE_WAN + ".bak"
BACKUP_FILE_VLANS = CONFIG_FILE_VLANS + ".bak"

async def get_iptables_line(chain, target):
    cmd = ["sudo", "iptables", "-L", chain, "-n", "--line-numbers"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    for line in result.stdout.split('\n'):
        if target in line:
            return int(line.split()[0])
    return None

async def check_iptables(table, chain, target, options=None):
    cmd = ["sudo", "iptables", "-t", table, "-L", chain, "-n", "--line-numbers"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return False, f"Error: {result.stderr}"
    
    if target in result.stdout:
        if options:
            if all(opt in result.stdout for opt in options):
                return True, f"Regla {target} encontrada con opciones {options}"
            else:
                return False, f"Regla {target} encontrada pero faltan opciones"
        return True, f"Regla {target} encontrada"
    return False, f"Regla {target} NO encontrada"

async def run_vlans_tests():
    print("--- Running VLANs Hierarchical Security Tests ---")
    
    if os.path.exists(CONFIG_FILE_VLANS):
        shutil.copy2(CONFIG_FILE_VLANS, BACKUP_FILE_VLANS)
    
    # Asegurar configuración limpia
    with open(CONFIG_FILE_VLANS, "w") as f:
        json.dump({"vlans": [], "status": 0}, f)

    if os.path.exists(CONFIG_FILE_WAN):
        shutil.copy2(CONFIG_FILE_WAN, BACKUP_FILE_WAN)
    
    try:
        # Mock WAN dependency to avoid modifying real routes
        print("0. Mocking WAN dependency...")
        with open(CONFIG_FILE_WAN, "w") as f:
            json.dump({"status": 1, "interface": "dummy-wan", "mode": "manual"}, f)

        print("\n1. Testing: vlans.config")
        vlans.config({"action": "add", "id": 10, "name": "VLAN10", "ip_interface": "10.10.10.1/24", "ip_network": "10.10.10.0/24"})
        
        print("\n2. Testing: vlans.start")
        ok, msg = vlans.start()
        print(f"Result: {ok}, Message: {msg}")

        # Verificar ausencia de ACCEPT en JSB_VLAN_STATS
        ok_acc, _ = await check_iptables("filter", "JSB_VLAN_STATS", "ACCEPT")
        print(f"NO ACCEPT rules in JSB_VLAN_STATS: {not ok_acc}")
       
        # Verificar ORDEN en JSB_GLOBAL_STATS / JSB_GLOBAL_ISOLATE
        pos_stats = await get_iptables_line("JSB_GLOBAL_STATS", "JSB_VLAN_STATS")
        pos_isolate = await get_iptables_line("JSB_GLOBAL_ISOLATE", "JSB_VLAN_ISOLATE")
        
        print(f"Hierarchy Check: STATS in GLOBAL_STATS pos={pos_stats}, ISOLATE in GLOBAL_ISOLATE pos={pos_isolate}")
        if pos_stats is not None and pos_isolate is not None:
            print("✅ VLAN hooks found in Global Chains")
        else:
            print("❌ VLAN hooks NOT found in Global Chains")

        # 3. isolate
        print("\n3. Testing: vlans.isolate --vlan 10")
        vlans.isolate({"vlan": 10})
        # Verificamos si existe la regla de DROP en JSB_VLAN_ISOLATE
        ok_r, _ = await check_iptables("filter", "JSB_VLAN_ISOLATE", "DROP")
        print(f"IPTables Check (Sub-chain ISOLATE): {ok_r}")

        # 4. top
        print("\n4. Testing: vlans.top")
        ok, msg = vlans.top()
        print(f"Stats result:\n{msg}")

        # 5. Stop
        print("\n5. Testing: vlans.stop")
        vlans.stop()

    finally:
        def sudo_rm(path):
            if os.path.exists(path): subprocess.run(["sudo", "rm", "-f", path], capture_output=True)
        def sudo_mv(src, dst):
            if os.path.exists(src): subprocess.run(["sudo", "mv", "-f", src, dst], capture_output=True)

        if BACKUP_FILE_VLANS:
            sudo_mv(BACKUP_FILE_VLANS, CONFIG_FILE_VLANS)
        else:
            sudo_rm(CONFIG_FILE_VLANS)
            
        if BACKUP_FILE_WAN:
            sudo_mv(BACKUP_FILE_WAN, CONFIG_FILE_WAN)
        else:
            sudo_rm(CONFIG_FILE_WAN)

if __name__ == "__main__":
    try:
        asyncio.run(run_vlans_tests())
        print("\n✅ Hierarchical VLANs Tests COMPLETED")
    except Exception as e:
        print(f"\n❌ Error: {e}")
