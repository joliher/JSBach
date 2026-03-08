import os
import re
import logging
from typing import Dict, Any, Tuple, Optional
from ...utils.global_helpers import (
    load_json_config, run_command
)

# Caminos absolutos
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CONFIG_DIR = os.path.join(BASE_DIR, "config", "wifi")
CONFIG_FILE = os.path.join(CONFIG_DIR, "wifi.json")
HOSTAPD_CONF = os.path.join(CONFIG_DIR, "hostapd.conf")

logger = logging.getLogger(__name__)

def is_ap_supported() -> Tuple[bool, str]:
    """
    Verifica si el sistema tiene alguna interfaz que soporte el modo AP (Access Point).
    Permite el uso de interfaces 'dummy' para pruebas.
    """
    try:
        # Check if the configured interface is a dummy interface for testing
        wifi_cfg = load_json_config(CONFIG_FILE, {})
        configured_iface = wifi_cfg.get("interface", "")
        if configured_iface.startswith("dummy"):
             logger.info(f"Omitiendo comprobación de hardware AP para interfaz de prueba: {configured_iface}")
             return True, f"Modo AP simulado para interfaz {configured_iface}"

        # Listar todos los phys inalámbricos
        success, output = run_command(["iw", "dev"], use_sudo=False)
        if not success or not output:
             return False, "No se detectaron interfaces inalámbricas"

        # Extraer nombres de phy (ej: phy0)
        phys = re.findall(r'phy#(\d+)', output)
        if not phys:
             return False, "No se detectaron PHYs inalámbricos"

        for phy_id in set(phys):
            success, info = run_command(["iw", f"phy", f"phy{phy_id}", "info"], use_sudo=False)
            if success and "AP" in info and "Supported interface modes" in info:
                # Verificar que 'AP' esté dentro de los modos soportados
                modes_section = False
                for line in info.split('\n'):
                    if "Supported interface modes" in line:
                        modes_section = True
                        continue
                    if modes_section:
                        if line.strip().startswith('*'):
                            if "AP" in line:
                                return True, f"Modo AP soportado en phy{phy_id}"
                        elif line.strip() == "":
                             modes_section = False
        
        return False, "Ninguna interfaz inalámbrica detectada soporta el modo AP"
    except Exception as e:
        logger.error(f"Error verificando soporte AP: {e}")
        return False, f"Error verificando hardware: {str(e)}"

def get_wifi_interface() -> Optional[str]:
    """
    Intenta detectar una interfaz Wi-Fi en el sistema.
    """
    success, output = run_command(["iw", "dev"], use_sudo=False)
    if success:
        match = re.search(r'Interface\s+([a-zA-Z0-9]+)', output)
        if match:
            return match.group(1)
    return None

def generate_hostapd_conf(wifi_cfg: Dict[str, Any]) -> str:
    """
    Genera el contenido de hostapd.conf basado en la seguridad elegida.
    """
    interface = wifi_cfg.get("interface") or get_wifi_interface() or "wlp3s0"
    ssid = wifi_cfg.get("ssid", "JSBach_WiFi")
    channel = wifi_cfg.get("channel", "6")
    hw_mode = wifi_cfg.get("hw_mode", "g")
    security = wifi_cfg.get("security", "wpa2")
    passphrase = wifi_cfg.get("password", "jsbach_secure_pass")
    
    lines = [
        f"interface={interface}",
        "driver=nl80211",
        f"ssid={ssid}",
        f"hw_mode={hw_mode}",
        f"channel={channel}",
        "wmm_enabled=1",
        "macaddr_acl=0",
        "auth_algs=1",
        "ignore_broadcast_ssid=0",
        "ieee80211n=1",
        "ctrl_interface=/var/run/hostapd"
    ]
    
    if hw_mode == 'a':
        lines.append("ieee80211ac=1")

    if security == "open":
        # No WPA lines needed
        pass
    elif security == "wpa2":
        lines.extend([
            "wpa=2",
            f"wpa_passphrase={passphrase}",
            "wpa_key_mgmt=WPA-PSK",
            "wpa_pairwise=TKIP",
            "rsn_pairwise=CCMP"
        ])
    elif security == "wpa3":
        lines.extend([
            "wpa=2",
            "wpa_key_mgmt=SAE",
            "rsn_pairwise=CCMP",
            "ieee80211w=2", # MFP mandatory
            f"sae_password={passphrase}"
        ])
    elif security == "mixed":
        lines.extend([
            "wpa=2",
            "wpa_key_mgmt=WPA-PSK SAE",
            "wpa_pairwise=TKIP",
            "rsn_pairwise=CCMP",
            "ieee80211w=1", # MFP optional but enabled
            f"wpa_passphrase={passphrase}",
            f"sae_password={passphrase}"
        ])
        
    return "\n".join(lines)
