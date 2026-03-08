#!/usr/bin/env python3
import sys
import os
import asyncio
import shutil
import subprocess

# Añadir el directorio raíz al path para importar módulos de JSBach
BASE_DIR = "/opt/JSBach_V4.2"
sys.path.append(BASE_DIR)

from app.modules.wan import wan

CONFIG_FILE_WAN = os.path.join(BASE_DIR, "config/wan/wan.json")
BACKUP_FILE_WAN = CONFIG_FILE_WAN + ".bak"
TEST_IFACE = "jsb-wan-test"

async def get_iptables_line(chain, target):
    cmd = ["sudo", "iptables", "-L", chain, "-n", "--line-numbers"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    for line in result.stdout.split('\n'):
        if target in line:
            parts = line.split()
            if parts[0].isdigit():
                return int(parts[0])
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

async def run_wan_tests():
    print(f"--- Running WAN Hierarchical Security Tests (Interface: {TEST_IFACE}) ---")
    
    # Crear interfaz de prueba
    subprocess.run(["sudo", "ip", "link", "add", TEST_IFACE, "type", "dummy"], capture_output=True)
    subprocess.run(["sudo", "ip", "link", "set", TEST_IFACE, "up"], capture_output=True)

    if os.path.exists(CONFIG_FILE_WAN):
        shutil.copy2(CONFIG_FILE_WAN, BACKUP_FILE_WAN)
    
    try:
        print(f"\n1. Testing: wan.config on {TEST_IFACE}")
        ok, msg = wan.config({"mode": "manual", "interface": TEST_IFACE, "ip": "10.255.255.2", "mask": "24", "gateway": "10.255.255.1", "dns": "8.8.8.8"})
        print(f"Config Result: {ok}, {msg}")
        
        print("\n2. Testing: wan.start")
        ok, msg = wan.start()
        print(f"Start Result: {ok}, {msg}")

        # Verificar ausencia de ACCEPT en JSB_WAN_STATS
        ok_acc, _ = await check_iptables("filter", "JSB_WAN_STATS", "ACCEPT")
        print(f"NO ACCEPT rules in JSB_WAN_STATS: {not ok_acc}")
       
        # Verificar ORDEN en JSB_GLOBAL_STATS / JSB_GLOBAL_ISOLATE
        # Nota: WAN hooks its module chains into JSB_GLOBAL_*
        pos_stats = await get_iptables_line("JSB_GLOBAL_STATS", "JSB_WAN_STATS")
        pos_isolate = await get_iptables_line("JSB_GLOBAL_ISOLATE", "JSB_WAN_ISOLATE")
        
        print(f"Hierarchy Check: STATS in GLOBAL_STATS pos={pos_stats}, ISOLATE in GLOBAL_ISOLATE pos={pos_isolate}")
        if pos_stats is not None and pos_isolate is not None:
            print("✅ WAN hooks found in Global Chains")
        else:
            print("❌ WAN hooks NOT found in Global Chains")

        # 3. Block
        print("\n3. Testing: wan.block --ip 192.168.100.50")
        wan.block({"ip": "192.168.100.50"})
        # Note: iptables -L -n usually shows the interface in a separate column or as 'out <iface>'
        # For simplicity, let's just check the IP and the chain
        ok_r, msg_r = await check_iptables("filter", "JSB_WAN_ISOLATE", "DROP", ["192.168.100.50"])
        print(f"IPTables Check (Sub-chain JSB_WAN_ISOLATE): {ok_r}, {msg_r}")

        # 4. Stop
        print("\n4. Testing: wan.stop")
        wan.stop()

    finally:
        # Cleanup
        subprocess.run(["sudo", "ip", "link", "del", TEST_IFACE], capture_output=True)
        if os.path.exists(BACKUP_FILE_WAN):
            subprocess.run(["sudo", "mv", "-f", BACKUP_FILE_WAN, CONFIG_FILE_WAN], capture_output=True)
        else:
            subprocess.run(["sudo", "rm", "-f", CONFIG_FILE_WAN], capture_output=True)

if __name__ == "__main__":
    try:
        asyncio.run(run_wan_tests())
        print("\n✅ Hierarchical WAN Tests COMPLETED")
    except Exception as e:
        print(f"\n❌ Error: {e}")
