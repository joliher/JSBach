import os
import ipaddress
from typing import List, Dict, Any, Tuple, Optional
from ...utils.global_helpers import (
    load_json_config, run_command, module_helpers as mh
)

# Caminos absolutos
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
VLAN_CONFIG_FILE = os.path.join(BASE_DIR, "config", "vlans", "vlans.json")

def get_active_vlans() -> List[Dict[str, Any]]:
    """Obtiene la lista de VLANs configuradas y activas."""
    cfg = load_json_config(VLAN_CONFIG_FILE, {"vlans": [], "status": 0})
    return cfg.get("vlans", [])

def generate_dnsmasq_conf(dhcp_cfg: Dict[str, Any]) -> Tuple[str, List[str]]:
    """
    Genera el contenido del fichero dnsmasq.conf basado en las VLANs
    y la configuración del módulo DHCP siguiendo el nuevo template.
    Retorna una tupla (contenido_config, lista_de_advertencias).
    """
    vlans = get_active_vlans()
    global_dns = dhcp_cfg.get("dns_servers", ["8.8.8.8", "8.8.4.4"])
    lease_time = dhcp_cfg.get("lease_time", "12h")
    warnings = []
    
    lines = [
        "# Generado automáticamente por JSBach DHCP Module",
        f"# Debug: vlan_configs keys = {list(dhcp_cfg.get('vlan_configs', {}).keys())}",
        "domain-needed",
        "bogus-priv",
        "no-resolv",
        "no-poll",
        "bind-interfaces",
        "cache-size=1000",
        ""
    ]
    
    # Configuración por cada VLAN
    for vlan in vlans:
        vlan_id = vlan.get("id")
        ip_int = vlan.get("ip_interface") # e.g. 10.0.1.1/24
        
        if not ip_int or "/" not in ip_int:
            continue
            
        try:
            iface_name = f"br0.{vlan_id}"
            
            # Verificar si la interfaz existe físicamente
            if not mh.interface_exists(iface_name):
                msg = f"La interfaz {iface_name} (VLAN {vlan_id}) no existe. DHCP omitido para esta red."
                warnings.append(msg)
                lines.append(f"# ADVERTENCIA: {msg}")
                lines.append("")
                continue

            ip_addr = ip_int.split("/")[0]
            network = ipaddress.IPv4Network(ip_int, strict=False)
            netmask = str(network.netmask)
            
            # Rangos y DNS específicos por VLAN
            vlan_configs = dhcp_cfg.get("vlan_configs", {})
            vlan_spec = vlan_configs.get(str(vlan_id), {})
            
            start_ip = vlan_spec.get("start", str(network.network_address + 100))
            end_ip = vlan_spec.get("end", str(network.network_address + 250))
            
            # DNS: usar el específico de la VLAN o el global
            vlan_dns = vlan_spec.get("dns", global_dns)
            if isinstance(vlan_dns, str):
                vlan_dns = [d.strip() for d in vlan_dns.split(",")]
            dns_str = ",".join(vlan_dns)
            
            lines.append(f"# VLAN {vlan_id}: {vlan.get('name')}")
            lines.append(f"interface={iface_name}")
            lines.append(f"dhcp-range={iface_name},{start_ip},{end_ip},{netmask},{lease_time}")
            lines.append(f"dhcp-option={iface_name},3,{ip_addr}")  # Gateway
            lines.append(f"dhcp-option={iface_name},6,{dns_str}")  # DNS
            lines.append("")
            
        except Exception as e:
            lines.append(f"# Error procesando VLAN {vlan_id}: {str(e)}")
            
    # Configuración para la interfaz Wi-Fi (si está activa)
    wifi_cfg_file = os.path.join(BASE_DIR, "config", "wifi", "wifi.json")
    if os.path.exists(wifi_cfg_file):
        try:
            wifi_cfg = load_json_config(wifi_cfg_file, {})
            if wifi_cfg.get("status") == 1:
                iface = wifi_cfg.get("interface", "wlp3s0")
                ip_addr = wifi_cfg.get("ip_address", "10.0.99.1")
                mask = wifi_cfg.get("netmask", "255.255.255.0")
                start_ip = wifi_cfg.get("dhcp_start", "10.0.99.100")
                end_ip = wifi_cfg.get("dhcp_end", "10.0.99.200")

                # Verificar si la interfaz existe físicamente
                if not mh.interface_exists(iface):
                    msg = f"La interfaz Wi-Fi {iface} no existe. DHCP omitido para Wi-Fi."
                    warnings.append(msg)
                    lines.append(f"# ADVERTENCIA: {msg}")
                    lines.append("")
                else:
                    lines.append("# Módulo Wi-Fi AP")
                    lines.append(f"interface={iface}")
                    lines.append(f"dhcp-range={iface},{start_ip},{end_ip},{mask},{lease_time}")
                    lines.append(f"dhcp-option={iface},3,{ip_addr}")
                    lines.append(f"dhcp-option={iface},6,{global_dns[0]}")
                    
                    # RFC 8910 / RFC 7710: Captive Portal identification
                    if wifi_cfg.get("portal_enabled", True):
                        portal_port = wifi_cfg.get("portal_port", 8500)
                        portal_url = f"http://{ip_addr}:{portal_port}/portal"
                        # Opción 114 (moderna) y 160 (antigua pero usada por Android/iOS)
                        lines.append(f"dhcp-option={iface},114,\"{portal_url}\"")
                        lines.append(f"dhcp-option={iface},160,\"{portal_url}\"")
                    
                    lines.append("")
        except Exception as e:
            lines.append(f"# Error procesando Wi-Fi: {str(e)}")
    
    return "\n".join(lines), warnings

def get_dnsmasq_pid() -> Optional[int]:
    """Busca el PID de dnsmasq si está corriendo con nuestra config."""
    pid_file = os.path.join(BASE_DIR, "config", "dhcp", "dnsmasq.pid")
    if not os.path.exists(pid_file):
        return None
        
    try:
        with open(pid_file, "r") as f:
            pid = int(f.read().strip())
            
        # Verificar que el proceso realmente existe y es dnsmasq
        success, output = run_command(["ps", "-p", str(pid), "-o", "comm="], use_sudo=False)
        if success and "dnsmasq" in output:
            return pid
    except:
        pass
    return None
