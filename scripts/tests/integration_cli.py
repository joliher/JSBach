#!/usr/bin/env python3
"""
=============================================================================
JSBach V4.7 - Master CLI Integration Test (Hybrid: Python + Expect)
=============================================================================
Objetivo:
  Replicar los mismos tests de scripts_general.py pero orquestando TODOS los
  módulos exclusivamente a través de la CLI interactiva de JSBach (TCP port 2200)
  mediante el script Expect master_cli_test.exp.

Arquitectura:
  1. Python (este script):
     - Crea las interfaces dummy (necesita sudo/root)
     - Pre-configura DHCP en disco (no tiene config vía CLI en este contexto)
     - Limpia el entorno de iptables
     - Lanza el script Expect
     - Verifica el estado final de iptables después de la ejecución del Expect
     - Limpia el entorno al terminar

  2. Expect (master_cli_test.exp):
     - Se conecta al CLI daemon de JSBach en 127.0.0.1:2200
     - Autentica con admin/password123
     - Configura WAN, VLANs, Wi-Fi, DMZ via CLI
     - Arranca todos los módulos en orden: wan vlans tagging wifi firewall dhcp dmz nat
     - Verifica el estado de los módulos
     - Aplica aislamiento sincronizado (VLAN 10 + Wi-Fi)
     - Para todos los módulos en orden inverso
     - Valida que cada operación devuelve ÉXITO

Uso:
  sudo /opt/JSBach/venv/bin/python3 scripts_general_cli.py
=============================================================================
"""

import os
import sys
import subprocess
import json
import time
import unittest

BASE_DIR = "/opt/JSBach"
EXP_SCRIPT = os.path.join(BASE_DIR, "app/modules/expect/scripts/master_cli_test.exp")
sys.path.append(BASE_DIR)

from app.utils.global_helpers import run_command, save_json_config


# ==============================================================================
# Fase 1: Helpers de infraestructura
# ==============================================================================

def deep_cleanup():
    """Limpia el entorno de iptables e interfaces virtuales."""
    print("[+] Limpiando entorno previo...")

    # Parar JSBach para que los módulos arranquen limpios
    subprocess.run(["systemctl", "stop", "jsbach"], capture_output=True)
    time.sleep(1)

    # Eliminar interfaces dummy previas
    for i in range(5):
        run_command([f"{__import__('shutil').which('ip') or '/usr/sbin/ip'}", "link", "del", f"dummy{i}"], ignore_error=True)
    run_command([f"{__import__('shutil').which('ip') or '/usr/sbin/ip'}", "link", "del", "br0"], ignore_error=True)

    # Limpiar cadenas JSB de iptables
    for table in ["filter", "nat", "mangle"]:
        run_command(["iptables", "-t", table, "-F"], ignore_error=True)
    run_command(["ebtables", "-F"], ignore_error=True)

    _, output = run_command(["iptables-save"])
    jsb_chains = [
        line.split()[1] for line in output.splitlines()
        if line.startswith(":") and "JSB" in line
    ]
    for chain in jsb_chains:
        run_command(["iptables", "-F", chain], ignore_error=True)
    for chain in reversed(jsb_chains):
        run_command(["iptables", "-X", chain], ignore_error=True)

    # Limpiar cualquier estado persistido en los JSON
    print("  > Borrando persistencia JSON...")
    for mod in ["wan", "vlans", "tagging", "wifi", "firewall", "dhcp", "dmz", "nat"]:
        cfg_path = os.path.join(BASE_DIR, f"config/{mod}/{mod}.json")
        if os.path.exists(cfg_path):
            save_json_config(cfg_path, {"status": 0})


def create_dummy_interfaces():
    """Crea las interfaces dummy para simular la red."""
    print("[+] Creando interfaces dummy...")
    interfaces = {
        "dummy0": "WAN",
        "dummy1": "VLANs",
        "dummy2": "Wi-Fi",
        "dummy3": "Tagging",
    }
    for iface, role in interfaces.items():
        run_command([f"{__import__('shutil').which('ip') or '/usr/sbin/ip'}", "link", "add", iface, "type", "dummy"])
        run_command([f"{__import__('shutil').which('ip') or '/usr/sbin/ip'}", "link", "set", iface, "up"])
        print(f"  > {iface}  ({role})")


def seed_dhcp_config():
    """
    Configura DHCP en disco.
    El comando 'dhcp config' no está disponible en la CLI de JSBach por diseño
    (se configura vía API/frontend). Lo sembramos directamente aquí.
    """
    print("[+] Sembrando configuracion de DHCP...")
    save_json_config(os.path.join(BASE_DIR, "config/dhcp/dhcp.json"), {
        "status": 0,
        "dns_servers": ["8.8.8.8", "1.1.1.1"],
        "lease_time": "12h",
        "vlan_configs": {
            "10": {
                "interface": "br0.10",
                "subnet": "10.0.10.0",
                "mask": "255.255.255.0",
                "range_start": "10.0.10.100",
                "range_end": "10.0.10.200",
                "gateway": "10.0.10.1"
            }
        }
    })


_cli_proc = None  # Global reference for the CLI server subprocess


def ensure_jsbach_running():
    """
    Asegura que el CLI daemon de JSBach esté activo en el puerto 2200.
    El servidor CLI es un proceso independiente del web server (puerto 8100),
    así que lo lanzamos explícitamente aquí.
    """
    global _cli_proc

    # Si ya hay algo escuchando en 2200, lo usamos directamente
    probe = subprocess.run(
        ["bash", "-c", "echo > /dev/tcp/127.0.0.1/2200"],
        capture_output=True
    )
    if probe.returncode == 0:
        print("[+] CLI server ya accesible en puerto 2200.")
        return

    print("[+] Arrancando CLI server en puerto 2200...")
    cli_cmd = [
        sys.executable,
        os.path.join(BASE_DIR, "app/cli/cli_server.py")
    ]
    with open("/tmp/cli_debug.log", "w") as cli_log:
        _cli_proc = subprocess.Popen(
            cli_cmd,
            cwd=BASE_DIR,
            stdout=cli_log,
            stderr=subprocess.STDOUT,
        )

    # Esperar hasta que el puerto responda
    for attempt in range(15):
        time.sleep(0.8)
        probe = subprocess.run(
            ["bash", "-c", "echo > /dev/tcp/127.0.0.1/2200"],
            capture_output=True
        )
        if probe.returncode == 0:
            print(f"    Puerto 2200 accesible (intento {attempt + 1}).")
            return
        print(f"    Esperando puerto 2200... (intento {attempt + 1}/15)")

    # Si no respondió, matar el proceso y reportar error
    if _cli_proc:
        _cli_proc.terminate()
    raise RuntimeError("El CLI de JSBach no está accesible en el puerto 2200.")



def cleanup_interfaces():
    """Elimina las interfaces dummy tras el test."""
    print("\n[+] Limpiando infraestructura virtual...")
    for i in range(5):
        run_command([f"{__import__('shutil').which('ip') or '/usr/sbin/ip'}", "link", "del", f"dummy{i}"], ignore_error=True)
    run_command([f"{__import__('shutil').which('ip') or '/usr/sbin/ip'}", "link", "del", "br0"], ignore_error=True)
    print("    Infraestructura limpiada.")


# ==============================================================================
# Fase 2: Prueba principal con verificación exhaustiva del kernel
# ==============================================================================

class TestMasterCLIIntegration(unittest.TestCase):
    """
    Orquesta la infraestructura y delega el flujo completo al script Expect.
    Se detiene a mitad del proceso para verificar EXHAUSTIVAMENTE el estado
    del kernel (iptables, ebtables, rutas, procesos).
    """

    @classmethod
    def setUpClass(cls):
        print("\n" + "=" * 60)
        print("  JSBach Master CLI Integration Test (Hardened)")
        print("=" * 60)
        
        # Limpiar ficheros de sincronización
        for f in ["/tmp/jsb_sync_ready", "/tmp/jsb_sync_continue"]:
            if os.path.exists(f): os.remove(f)
            
        deep_cleanup()
        create_dummy_interfaces()
        seed_dhcp_config()
        ensure_jsbach_running()

    @classmethod
    def tearDownClass(cls):
        cleanup_interfaces()
        # Limpiar ficheros de sincronización
        for f in ["/tmp/jsb_sync_ready", "/tmp/jsb_sync_continue"]:
            if os.path.exists(f): os.remove(f)
            
        # Terminar el CLI server si lo arrancamos nosotros
        global _cli_proc
        if _cli_proc and _cli_proc.poll() is None:
            _cli_proc.terminate()
            _cli_proc.wait(timeout=5)
            print("[+] CLI server detenido.")
        # Reiniciar jsbach web server para limpiar cualquier estado residual
        subprocess.run(["systemctl", "restart", "jsbach"], capture_output=True)
        print("[+] jsbach.service reiniciado.")

    def _verify_kernel_state(self):
        """EXHAUSTIVE KERNEL INSPECTION: Valida que la CLI tradujo correctamente a reglas de Linux."""
        print("\n[+] INICIANDO VERIFICACION EXHAUSTIVA DEL KERNEL...")

        # 1. IP Y RUTAS (WAN & VLANs)
        _, addr_out = run_command(["ip", "addr"])
        self.assertIn("192.168.100.2", addr_out, "IP WAN no encontrada")
        self.assertIn("10.0.10.1", addr_out, "IP VLAN 10 no encontrada")
        self.assertIn("10.0.20.1", addr_out, "IP VLAN 20 no encontrada")
        self.assertIn("10.0.99.1", addr_out, "IP Wi-Fi no encontrada")
        print("    ✅ IPs asignadas correctamente.")

        # 2. BRIDGE VLAN (Tagging)
        _, br_out = run_command(["bridge", "vlan", "show"])
        self.assertIn("dummy3", br_out, "dummy3 no está en el bridge")
        self.assertTrue(any("10 PVID" in l for l in br_out.splitlines() if "dummy3" in l), "PVID 10 no asignada a dummy3")
        print("    ✅ Tagging L2 configurado en kernel.")

        # 3. NAT & DMZ (Table nat)
        _, nat_out = run_command(["iptables", "-t", "nat", "-S"])
        self.assertTrue(any("-o dummy0" in l and "MASQUERADE" in l for l in nat_out.splitlines()), "Regla MASQUERADE no encontrada")
        
        # DMZ DNAT
        self.assertTrue(any("DNAT" in l and "10.0.20.10" in l and "dport 80" in l for l in nat_out.splitlines()), "Regla DNAT (DMZ) no encontrada")
        
        # DMZ Isolation (Aislamiento de host)
        self.assertTrue(any("JSB_DMZ_ISOLATE" in l and "10.0.20.10" in l and "RETURN" in l for l in nat_out.splitlines()), "Excepción de aislamiento DMZ no encontrada")
        print("    ✅ Reglas NAT y DMZ activas.")

        # 4. FIREWALL (Aislamientos y Restricciones L3)
        _, fw_out = run_command(["iptables", "-S"])
        
        # VLAN 10 Aislada
        self.assertTrue(any("JSB_FW_ISOLATE" in l and "10.0.10.0/24" in l and "DROP" in l for l in fw_out.splitlines()), "VLAN 10 no aislada")
        # Wi-Fi Aislado (Módulo)
        self.assertTrue(any("FORWARD_WIFI" in l and "DROP" in l for l in fw_out.splitlines()), "Wi-Fi no aislado")
        
        # VLAN 20 Restringida
        self.assertTrue(any("INPUT_VLAN_20" in l and "67" in l and "RETURN" in l for l in fw_out.splitlines()), "DHCP ignore en VLAN 20 falló")
        self.assertTrue(any("INPUT_VLAN_20" in l and "DROP" in l for l in fw_out.splitlines()), "Política DROP en VLAN 20 falló")
        
        # VLAN 10 Whitelist (FORWARD_VLAN_10 debe terminar en DROP si la whitelist está vacía)
        self.assertTrue(any("FORWARD_VLAN_10" in l and "DROP" in l for l in fw_out.splitlines()), "Whitelist en VLAN 10 (DROP) falló")
        
        print("    ✅ Aislamientos, Restricciones y Whitelist L3 verificados.")

        # 5. EBTABLES (Aislamiento L2)
        _, ebt_out = run_command(["ebtables", "-L"])
        self.assertIn("-i dummy3 -j DROP", ebt_out, "Aislamiento L2 Entrante dummy3")
        self.assertIn("-o dummy3 -j DROP", ebt_out, "Aislamiento L2 Saliente dummy3")
        print("    ✅ Aislamiento L2 verificado.")

        # 6. WI-FI (Configuración, PID, Cadenas iptables)
        hostapd_conf = os.path.join(BASE_DIR, "config/wifi/hostapd.conf")
        self.assertTrue(os.path.exists(hostapd_conf), "hostapd.conf no generado")
        
        hostapd_pid = os.path.join(BASE_DIR, "config/wifi/hostapd.pid")
        self.assertTrue(os.path.exists(hostapd_pid), "hostapd.pid no existe")
        
        # Verificar contenido del hostapd.conf (SSID configurado)
        with open(hostapd_conf) as f:
            hconf = f.read()
        self.assertIn("ssid=TestNet", hconf, "SSID no configurado en hostapd.conf")
        
        # Cadenas Wi-Fi en iptables (FORWARD_WIFI e INPUT_WIFI son creadas por firewall)
        self.assertTrue(any("FORWARD_WIFI" in l for l in fw_out.splitlines()), "Cadena FORWARD_WIFI no existe")
        self.assertTrue(any("INPUT_WIFI" in l for l in fw_out.splitlines()), "Cadena INPUT_WIFI no existe")
        
        # INPUT_WIFI con restricción (DROP al router)
        self.assertTrue(any("INPUT_WIFI" in l and "DROP" in l for l in fw_out.splitlines()), "Wi-Fi no restringido (INPUT_WIFI)")
        print("    ✅ Módulo Wi-Fi verificado (config, PID, cadenas iptables).")

        # 7. PROCESOS (DHCP)
        _, ps_out = run_command(["ps", "aux"])
        self.assertIn("dnsmasq", ps_out, "Proceso dnsmasq no activo")
        print("    ✅ Proceso DHCP activo.")

    def test_01_hardened_cli_lifecycle(self):
        """Flujo completo con sincronización para verificación del kernel."""
        print("\n[+] Iniciando ciclo de vida CLI con Hardening...")
        
        p = subprocess.Popen(
            ["/usr/bin/expect", "-f", EXP_SCRIPT],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        try:
            sync_detected = False
            start_time = time.time()
            
            # Leer salida de Expect hasta llegar al punto de sincronización
            while p.poll() is None:
                line = p.stdout.readline()
                if not line:
                    if time.time() - start_time > 60: break
                    time.sleep(0.1)
                    continue
                
                if "SINCRONIZACION: Esperando verificacion del kernel" in line:
                    print("  > Punto de sincronización detectado.")
                    sync_detected = True
                    break

            if not sync_detected:
                 self.fail("Expect falló o terminó antes de alcanzar el punto de sincronización.")

            # Realizar verificaciones del kernel
            self._verify_kernel_state()

            # Continuar con el Teardown
            print("\n[+] Verificación ok. Enviando señal de continuación...")
            with open("/tmp/jsb_sync_continue", "w") as f:
                f.write("GO")

            # Esperar fin
            out, _ = p.communicate(timeout=60)
            self.assertEqual(p.returncode, 0, f"Expect falló en el Teardown. Salida:\n{out}")
            
        finally:
            if p.poll() is None:
                p.terminate()
                p.wait()

    def test_02_post_cleanup_state(self):
        """Verifica que tras el stop de Expect, el kernel vuelve a estado limpio."""
        print("\n[+] Verificando limpieza post-test...")
        
        # Volver al check de iptables limpio (solo Global Infra)
        _, output = run_command(["iptables", "-S"])
        GLOBAL_INFRA = {"JSB_GLOBAL_RESTRICT", "JSB_GLOBAL_STATS", "JSB_GLOBAL_ISOLATE",
                        "JSB_GLOBAL_PRE", "JSB_GLOBAL_NAT"}
        
        residual = [
            l for l in output.splitlines()
            if "JSB" in l and l.startswith("-A") and not any(g in l for g in GLOBAL_INFRA)
        ]
        self.assertEqual(len(residual), 0, f"Reglas residuales: {residual}")
        
        # Verificar Zero-Disk
        volatile = [
            os.path.join(BASE_DIR, "config/dhcp/dnsmasq.conf"),
            os.path.join(BASE_DIR, "config/wifi/hostapd.conf")
        ]
        self.assertEqual(len([f for f in volatile if os.path.exists(f)]), 0, "Ficheros config residuales")
        print("    ✅ Sistema limpio.")

# ==============================================================================
if __name__ == "__main__":
    unittest.main(verbosity=2)
