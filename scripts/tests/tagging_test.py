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

from app.modules.tagging import tagging

CONFIG_FILE_TAGGING = os.path.join(BASE_DIR, "config/tagging/tagging.json")
BACKUP_FILE_TAGGING = CONFIG_FILE_TAGGING + ".bak"
TEST_IFACE = "jsb-tag-if1"

async def check_ebtables(chain, target, options=None):
    # Usar sudo -n para evitar colgarse, aunque lo lanzaremos con sudo desde fuera
    cmd = ["sudo", "-n", "ebtables", "-L", chain, "--Ln"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return False, f"Error: {result.stderr.strip()}"
    
    # Normalizar salida para evitar problemas con espacios
    for line in result.stdout.split('\n'):
        if target in line:
            if options:
                if all(opt in line for opt in options):
                    return True, f"Regla {target} encontrada con opciones {options}"
                continue # Buscar otra línea que coincida si esta no tiene las opciones
            return True, f"Regla {target} encontrada"
    return False, f"Regla {target} NO encontrada"

async def run_tagging_tests():
    print(f"--- Running Tagging Security Tests (Interface: {TEST_IFACE}) ---")
    
    # 0. Preparar entorno (Dummy IF + Bridge real para que pase los checks)
    print("0. Preparando infraestructura de red dummy...")
    res = subprocess.run(["sudo", "-n", "ip", "link", "add", TEST_IFACE, "type", "dummy"], capture_output=True, text=True)
    if res.returncode != 0 and "File exists" not in res.stderr:
        print(f"ERROR creando {TEST_IFACE}: {res.stderr}")
        return

    subprocess.run(["sudo", "-n", "ip", "link", "set", TEST_IFACE, "up"], capture_output=True)
    
    res = subprocess.run(["sudo", "-n", "ip", "link", "add", "br0", "type", "bridge"], capture_output=True, text=True)
    if res.returncode != 0 and "File exists" not in res.stderr:
        print(f"ERROR creando br0: {res.stderr}")
        # Intentar continuar si ya existe

    subprocess.run(["sudo", "-n", "ip", "link", "set", "br0", "up"], capture_output=True)

    # Mock VLANs dependency
    VLAN_CONFIG_DIR = os.path.join(BASE_DIR, "config/vlans")
    VLAN_CONFIG_FILE = os.path.join(VLAN_CONFIG_DIR, "vlans.json")
    os.makedirs(VLAN_CONFIG_DIR, exist_ok=True)
    
    VLAN_BACKUP = None
    if os.path.exists(VLAN_CONFIG_FILE):
        VLAN_BACKUP = VLAN_CONFIG_FILE + ".testbak"
        shutil.copy2(VLAN_CONFIG_FILE, VLAN_BACKUP)
    
    with open(VLAN_CONFIG_FILE, "w") as f:
        json.dump({"status": 1, "vlans": [{"id": 10, "name": "test"}]}, f)

    if os.path.exists(CONFIG_FILE_TAGGING):
        shutil.copy2(CONFIG_FILE_TAGGING, BACKUP_FILE_TAGGING)
    
    # Asegurar configuración limpia para evitar errores de interfaces inexistentes (dummy3, etc)
    with open(CONFIG_FILE_TAGGING, "w") as f:
        json.dump({"interfaces": [], "status": 0}, f)

    try:
        # 1. Configurar puerto en Access (VLAN 10)
        print(f"\n1. Testing: tagging.config add {TEST_IFACE}")
        tagging.config({"action": "add", "name": TEST_IFACE, "vlan_untag": "10"})
        
        # 2. Iniciar (Crea cadenas ebtables)
        print("\n2. Testing: tagging.start")
        ok, msg = tagging.start()
        print(f"Result: {ok}, {msg}")
        
        # Verificar saltos en FORWARD L2 (Jerárquico: FORWARD -> GLOBAL -> MODULE)
        ok_g, _ = await check_ebtables("FORWARD", "JSB_GLOBAL_EBT_ISOLATE")
        ok_m, _ = await check_ebtables("JSB_GLOBAL_EBT_ISOLATE", "JSB_TAG_ISOLATE")
        print(f"Jump to JSB_TAG_ISOLATE in FORWARD L2: {ok_g and ok_m}")
        
        ok_g, _ = await check_ebtables("FORWARD", "JSB_GLOBAL_EBT_STATS")
        ok_m, _ = await check_ebtables("JSB_GLOBAL_EBT_STATS", "JSB_TAG_STATS")
        print(f"Jump to JSB_TAG_STATS in FORWARD L2: {ok_g and ok_m}")

        # 3. Isolate
        print(f"\n3. Testing: tagging.isolate {TEST_IFACE}")
        tagging.isolate({"iface": TEST_IFACE})
        ok_r, msg_r = await check_ebtables("JSB_TAG_ISOLATE", "DROP", ["-i " + TEST_IFACE])
        print(f"Rule in JSB_TAG_ISOLATE (IN): {ok_r}")
        ok_r, msg_r = await check_ebtables("JSB_TAG_ISOLATE", "DROP", ["-o " + TEST_IFACE])
        print(f"Rule in JSB_TAG_ISOLATE (OUT): {ok_r}")

        # 4. Traffic Log
        print(f"\n4. Testing: tagging.traffic_log {TEST_IFACE}")
        tagging.traffic_log({"iface": TEST_IFACE, "status": "on"})
        # ebtables (nf_tables) muestra --log-prefix en el listado
        ok_r, _ = await check_ebtables("JSB_TAG_STATS", TEST_IFACE, ["--log-prefix", "[JSB-TAG-OUT]"])
        print(f"Log rule in JSB_TAG_STATS: {ok_r}")

        # 5. Top
        print("\n5. Testing: tagging.top")
        ok, stats = tagging.top()
        print("(Nota: 0 paquetes/bytes es normal en interfaces dummy sin generador de tráfico)")
        print(stats)

        # 6. Stop
        print("\n6. Testing: tagging.stop")
        tagging.stop()

    finally:
        def sudo_rm(path):
            if os.path.exists(path): subprocess.run(["sudo", "-n", "rm", "-f", path], capture_output=True)
        def sudo_mv(src, dst):
            if os.path.exists(src): subprocess.run(["sudo", "-n", "mv", "-f", src, dst], capture_output=True)

        # Cleanup
        subprocess.run(["sudo", "-n", "ip", "link", "del", TEST_IFACE], capture_output=True)
        subprocess.run(["sudo", "-n", "ip", "link", "del", "br0"], capture_output=True)
        
        # Cleanup VLAN mock
        if VLAN_BACKUP:
            sudo_mv(VLAN_BACKUP, VLAN_CONFIG_FILE)
        elif os.path.exists(VLAN_CONFIG_FILE):
            sudo_rm(VLAN_CONFIG_FILE)

        if BACKUP_FILE_TAGGING and os.path.exists(BACKUP_FILE_TAGGING):
            sudo_mv(BACKUP_FILE_TAGGING, CONFIG_FILE_TAGGING)
        elif os.path.exists(CONFIG_FILE_TAGGING):
            sudo_rm(CONFIG_FILE_TAGGING)

if __name__ == "__main__":
    try:
        asyncio.run(run_tagging_tests())
        print("\n✅ Tagging Hierarchical Tests COMPLETED")
    except Exception as e:
        print(f"\n❌ Error: {e}")
