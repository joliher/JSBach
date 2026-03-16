#!/usr/bin/env python3
import sys
import os
import asyncio
import shutil
import subprocess
import json

# Añadir el directorio raíz al path para importar módulos de JSBach
BASE_DIR = "/opt/JSBach"
sys.path.append(BASE_DIR)

from app.modules.firewall import firewall

CONFIG_FILE_FW = os.path.join(BASE_DIR, "config/firewall/firewall.json")
BACKUP_FILE_FW = CONFIG_FILE_FW + ".bak"
TEST_VLAN_ID = 20
TEST_IP = "10.0.20.0/24"

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
    print(result.stdout); return False, f"Regla {target} NO encontrada"

async def run_firewall_tests():
    print(f"--- Running Firewall Security Tests (VLAN: {TEST_VLAN_ID}) ---")
    
    # Mock VLANs dependency
    VLAN_CONFIG_DIR = os.path.join(BASE_DIR, "config/vlans")
    VLAN_CONFIG_FILE = os.path.join(VLAN_CONFIG_DIR, "vlans.json")
    os.makedirs(VLAN_CONFIG_DIR, exist_ok=True)
    
    VLAN_BACKUP = None
    # Mock Tagging dependency
    TAG_CONFIG_DIR = os.path.join(BASE_DIR, "config/tagging")
    TAG_CONFIG_FILE = os.path.join(TAG_CONFIG_DIR, "tagging.json")
    os.makedirs(TAG_CONFIG_DIR, exist_ok=True)
    TAG_BACKUP = None
    if os.path.exists(TAG_CONFIG_FILE):
        TAG_BACKUP = TAG_CONFIG_FILE + ".testbak"
        shutil.copy2(TAG_CONFIG_FILE, TAG_BACKUP)
    with open(TAG_CONFIG_FILE, "w") as f:
        json.dump({"status": 1, "interfaces": []}, f)

    if os.path.exists(VLAN_CONFIG_FILE):
        VLAN_BACKUP = VLAN_CONFIG_FILE + ".testbak"
        shutil.copy2(VLAN_CONFIG_FILE, VLAN_BACKUP)
    
    with open(VLAN_CONFIG_FILE, "w") as f:
        json.dump({"status": 1, "vlans": [{"id": TEST_VLAN_ID, "name": "test", "ip_network": TEST_IP}]}, f)

    if os.path.exists(CONFIG_FILE_FW):
        shutil.copy2(CONFIG_FILE_FW, BACKUP_FILE_FW)
    
    # Asegurar configuración limpia
    with open(CONFIG_FILE_FW, "w") as f:
        json.dump({"vlans": {}, "status": 0}, f)
    
    # Mock WAN dependency
    CONFIG_FILE_WAN = os.path.join(BASE_DIR, "config/wan/wan.json")
    WAN_BACKUP = None
    if os.path.exists(CONFIG_FILE_WAN):
        WAN_BACKUP = CONFIG_FILE_WAN + ".testbak_fw"
        shutil.copy2(CONFIG_FILE_WAN, WAN_BACKUP)
    
    with open(CONFIG_FILE_WAN, "w") as f:
        json.dump({"status": 1, "interface": "dummy-wan", "mode": "manual"}, f)

    try:
        print("\n1. Testing: firewall.start")
        ok, msg = firewall.start()
        print(f"Start Result: {ok}, {msg}")

        # Verificar ausencia de ACCEPT en JSB_FW_STATS
        ok_acc, _ = await check_iptables("filter", "JSB_FW_STATS", "ACCEPT")
        print(f"NO ACCEPT rules in JSB_FW_STATS: {not ok_acc}")
       
        # Verificar cadenas base (deben tener RETURN o estar vacías, NUNCA ACCEPT)
        for chain in ["JSB_FW_STATS", "JSB_FW_ISOLATE", "JSB_FW_RESTRICT"]:
            ok_r, _ = await check_iptables("filter", chain, "RETURN")
            # Un módulo nunca debe tener política ACCEPT en sus cadenas
            # ebtables/iptables chains have policy/return default
            # A chain exists if -L doesn't fail
            res = subprocess.run(["sudo", "iptables", "-L", chain], capture_output=True)
            print(f"Chain {chain} exists: {res.returncode == 0}")

        # 2. Isolate
        print(f"\n2. Testing: firewall.isolate vlan_id={TEST_VLAN_ID}")
        firewall.isolate({"vlan_id": TEST_VLAN_ID})
        
        # Verificar saltos en JSB_GLOBAL_ISOLATE (V4.2 usa JSB_FW_ISOLATE)
        ok_hook, _ = await check_iptables("filter", "JSB_GLOBAL_ISOLATE", "JSB_FW_ISOLATE")
        print(f"Jump to JSB_FW_ISOLATE in JSB_GLOBAL_ISOLATE: {ok_hook}")
        
        # En v4.2, isolate inserta en JSB_FW_ISOLATE con la red IP de la VLAN
        ok_d, _ = await check_iptables("filter", "JSB_FW_ISOLATE", "DROP", [TEST_IP.split('/')[0]])
        print(f"DROP rule for network {TEST_IP} in JSB_FW_ISOLATE: {ok_d}")

        # 3. Restrict
        print(f"\n3. Testing: firewall.restrict vlan_id={TEST_VLAN_ID}")
        firewall.restrict({"vlan_id": TEST_VLAN_ID})
        # Restrict crea una cadena dinámica INPUT_VLAN_<ID>
        chain_vlan = f"INPUT_VLAN_{TEST_VLAN_ID}"
        ok_l, _ = await check_iptables("filter", chain_vlan, "LOG", ["[JSB-FW-RESTRICT]"])
        ok_d, _ = await check_iptables("filter", chain_vlan, "DROP")
        print(f"LOG rule in {chain_vlan}: {ok_l}")
        print(f"DROP rule in {chain_vlan}: {ok_d}")

        # 4. Traffic Log
        print(f"\n4. Testing: firewall.traffic_log vlan_id={TEST_VLAN_ID}")
        firewall.traffic_log({"vlan_id": TEST_VLAN_ID, "status": "on"})
        # Traffic log en v4.2 inyecta en JSB_FW_STATS
        ok_l, _ = await check_iptables("filter", "JSB_FW_STATS", "LOG", ["[JSB-FW-LOG]"])
        print(f"LOG rule in JSB_FW_STATS: {ok_l}")

        # 5. Top
        print("\n5. Testing: firewall.top")
        ok, stats = firewall.top()
        print(f"Top stats successful: {ok}")

        # 6. Stop
        print("\n6. Testing: firewall.stop")
        firewall.stop()

    finally:
        # Cleanup with sudo to avoid permission denied on root-owned configs
        def sudo_rm(path):
            if os.path.exists(path):
                subprocess.run(["sudo", "rm", "-f", path], capture_output=True)

        def sudo_mv(src, dst):
            if os.path.exists(src):
                subprocess.run(["sudo", "mv", "-f", src, dst], capture_output=True)

        # Cleanup VLAN mock
        if VLAN_BACKUP:
            sudo_mv(VLAN_BACKUP, VLAN_CONFIG_FILE)
        else:
            sudo_rm(VLAN_CONFIG_FILE)

        # Cleanup Tagging mock
        if TAG_BACKUP:
            sudo_mv(TAG_BACKUP, TAG_CONFIG_FILE)
        else:
            sudo_rm(TAG_CONFIG_FILE)

        # Cleanup WAN mock
        if WAN_BACKUP:
            sudo_mv(WAN_BACKUP, CONFIG_FILE_WAN)
        else:
            sudo_rm(CONFIG_FILE_WAN)

        # Cleanup Firewall backup
        if os.path.exists(BACKUP_FILE_FW):
            sudo_mv(BACKUP_FILE_FW, CONFIG_FILE_FW)

if __name__ == "__main__":
    try:
        asyncio.run(run_firewall_tests())
        print("\n✅ Firewall Hierarchical Tests COMPLETED")
    except Exception as e:
        print(f"\n❌ Error: {e}")
