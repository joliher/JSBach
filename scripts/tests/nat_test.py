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

from app.modules.nat import nat

CONFIG_FILE_NAT = os.path.join(BASE_DIR, "config/nat/nat.json")
BACKUP_FILE_NAT = CONFIG_FILE_NAT + ".bak"
TEST_IFACE = "jsb-nat-test"

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

async def run_nat_tests():
    print(f"--- Running NAT Hierarchical Security Tests (Interface: {TEST_IFACE}) ---")
    
    # Crear interfaz de prueba
    subprocess.run(["sudo", "ip", "link", "add", TEST_IFACE, "type", "dummy"], capture_output=True)
    subprocess.run(["sudo", "ip", "link", "set", TEST_IFACE, "up"], capture_output=True)

    if os.path.exists(CONFIG_FILE_NAT):
        shutil.copy2(CONFIG_FILE_NAT, BACKUP_FILE_NAT)
    
    # Mock WAN dependency
    CONFIG_FILE_WAN = os.path.join(BASE_DIR, "config/wan/wan.json")
    WAN_BACKUP = None
    if os.path.exists(CONFIG_FILE_WAN):
        WAN_BACKUP = CONFIG_FILE_WAN + ".testbak_nat"
        shutil.copy2(CONFIG_FILE_WAN, WAN_BACKUP)
    
    with open(CONFIG_FILE_WAN, "w") as f:
        json.dump({"status": 1, "interface": "dummy-wan", "mode": "manual"}, f)

    try:
        # 1. Configurar
        print(f"\n1. Testing: nat.config (using {TEST_IFACE})")
        nat.config({"interface": TEST_IFACE})
        
        # 2. Iniciar
        print("\n2. Testing: nat.start")
        ok, msg = nat.start()
        print(f"Result: {ok}, Message: {msg}")
        
        # Verificar saltos en JSB_GLOBAL_ISOLATE y JSB_GLOBAL_NAT
        ok_r, _ = await check_iptables("filter", "JSB_GLOBAL_ISOLATE", "JSB_NAT_ISOLATE")
        print(f"Jump to JSB_NAT_ISOLATE in JSB_GLOBAL_ISOLATE: {ok_r}")
        
        ok_r, _ = await check_iptables("nat", "JSB_GLOBAL_NAT", "JSB_NAT_STATS")
        print(f"Jump to JSB_NAT_STATS in JSB_GLOBAL_NAT: {ok_r}")

        # Comprobar que JSB_NAT_ISOLATE no tiene ACCEPT (debería tener RETURN o vacía)
        ok_no_accept_isolate, _ = await check_iptables("filter", "JSB_NAT_ISOLATE", "ACCEPT")
        print(f"NO ACCEPT rules in JSB_NAT_ISOLATE: {not ok_no_accept_isolate}")

        # Comprobar que JSB_NAT_STATS no tiene ACCEPT (debería tener RETURN o vacía)
        ok_no_accept_stats, _ = await check_iptables("nat", "JSB_NAT_STATS", "ACCEPT")
        print(f"NO ACCEPT rules in JSB_NAT_STATS: {not ok_no_accept_stats}")

        # 3. Block
        print("\n3. Testing: nat.block --ip 1.2.3.4")
        nat.block({"ip": "1.2.3.4"})
        ok_r, msg_r = await check_iptables("filter", "JSB_NAT_ISOLATE", "DROP", ["1.2.3.4"])
        print(f"Rule in JSB_NAT_ISOLATE: {ok_r}")

        # 4. Stop
        print("\n4. Testing: nat.stop")
        nat.stop()

    finally:
        # Cleanup
        subprocess.run(["sudo", "ip", "link", "del", TEST_IFACE], capture_output=True)
        
        def sudo_rm(path):
            if os.path.exists(path): subprocess.run(["sudo", "rm", "-f", path], capture_output=True)
        def sudo_mv(src, dst):
            if os.path.exists(src): subprocess.run(["sudo", "mv", "-f", src, dst], capture_output=True)

        if WAN_BACKUP:
            sudo_mv(WAN_BACKUP, CONFIG_FILE_WAN)
        else:
            sudo_rm(CONFIG_FILE_WAN)

        if os.path.exists(BACKUP_FILE_NAT):
            sudo_mv(BACKUP_FILE_NAT, CONFIG_FILE_NAT)

if __name__ == "__main__":
    try:
        asyncio.run(run_nat_tests())
        print("\n✅ Hierarchical NAT Tests COMPLETED")
    except Exception as e:
        print(f"\n❌ Error: {e}")
