import os
import sys
import time
import json
import subprocess
import unittest
from typing import Dict, Any

# Añadir el raíz del proyecto al path
BASE_DIR = "/opt/JSBach_V4.2"
sys.path.append(BASE_DIR)

from app.modules.wifi import wifi
from app.utils.global_helpers import run_command, load_json_config

class TestWifiLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Asegurar que el directorio de configuración existe
        os.makedirs(os.path.join(BASE_DIR, "config", "wifi"), exist_ok=True)
        # Configuración de prueba con interfaz dummy
        cls.test_cfg = {
            "ssid": "JSBach_Test",
            "password": "test_password_secure",
            "channel": "1",
            "interface": "dummy0",
            "ip_address": "10.0.99.1",
            "netmask": "255.255.255.0",
            "portal_enabled": True,
            "portal_port": 8501
        }
        with open(os.path.join(BASE_DIR, "config", "wifi", "wifi.json"), "w") as f:
            json.dump(cls.test_cfg, f)

    def test_01_start_lifecycle(self):
        """Verificar el inicio del servicio y subprocesos."""
        print("\n[+] Iniciando servicio Wi-Fi (Dummy)...")
        success, msg = wifi.start()
        self.assertTrue(success, f"Error al iniciar: {msg}")
        
        # Verificar archivos
        self.assertTrue(os.path.exists(wifi.HOSTAPD_CONF), "Falta hostapd.conf")
        # El PID_FILE se crea incluso en modo dummy en mi refactor
        self.assertTrue(os.path.exists(wifi.PID_FILE), "Falta hostapd.pid")
        
        # Verificar subprocesos (Portal)
        portal_pid_file = os.path.join(wifi.CONFIG_DIR, "portal_server.pid")
        self.assertTrue(os.path.exists(portal_pid_file), "Falta portal_server.pid")
        
        # Verificar status
        s_ok, s_msg = wifi.status()
        print(f"[*] Status: {s_msg}")
        self.assertIn("ACTIVO", s_msg)
        self.assertIn("JSBach_Test", s_msg)

    def test_02_firewall_rules(self):
        """Verificar la inyección de reglas jerárquicas en iptables."""
        print("[+] Verificando reglas de firewall...")
        
        # Verificar hook en JSB_GLOBAL_RESTRICT
        success, output = run_command(["sudo", "iptables", "-L", "JSB_GLOBAL_RESTRICT", "-n"])
        self.assertIn("INPUT_WIFI", output, "Hook INPUT_WIFI no encontrado en JSB_GLOBAL_RESTRICT")
        
        # Verificar hook en JSB_GLOBAL_ISOLATE
        success, output = run_command(["sudo", "iptables", "-L", "JSB_GLOBAL_ISOLATE", "-n"])
        self.assertIn("FORWARD_WIFI", output, "Hook FORWARD_WIFI no encontrado en JSB_GLOBAL_ISOLATE")
        
        # Verificar reglas dentro de INPUT_WIFI (RETURN en lugar de ACCEPT)
        success, output = run_command(["sudo", "iptables", "-L", "INPUT_WIFI", "-n"])
        self.assertIn("RETURN", output, "No se encontraron reglas RETURN en INPUT_WIFI")
        self.assertIn("LOG", output, "No se encontró regla de LOG en INPUT_WIFI")
        
        # Verificar portal redirect en NAT
        success, output = run_command(["sudo", "iptables", "-t", "nat", "-L", "WIFI_PORTAL_REDIRECT", "-n"])
        self.assertIn("DNAT", output, "Regla de redirección del portal no encontrada en NAT")

    def test_03_stop_cleanup(self):
        """Verificar la parada y limpieza Zero-Disk."""
        print("[+] Deteniendo servicio Wi-Fi...")
        success, msg = wifi.stop()
        self.assertTrue(success, f"Error al detener: {msg}")
        
        # Verificar limpieza de archivos
        self.assertFalse(os.path.exists(wifi.HOSTAPD_CONF), "hostapd.conf no fue eliminado")
        self.assertFalse(os.path.exists(wifi.PID_FILE), "hostapd.pid no fue eliminado")
        
        portal_pid_file = os.path.join(wifi.CONFIG_DIR, "portal_server.pid")
        self.assertFalse(os.path.exists(portal_pid_file), "portal_server.pid no fue eliminado")
        
        # Verificar status final
        s_ok, s_msg = wifi.status()
        self.assertIn("INACTIVO", s_msg)

if __name__ == "__main__":
    unittest.main()

