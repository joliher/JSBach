# app/core/helpers/helper_firewall.py
# Helper functions for Firewall module
# Extracted from app/core/firewall.py

import os
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
import re
import json
import logging
from typing import Tuple, List
from ...utils.global_helpers import module_helpers as mh, io_helpers as ioh
from ...utils.global_helpers import load_json_config, save_json_config, run_command

logger = logging.getLogger(__name__)

# ==========================================
# Configuration
# ==========================================

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
FIREWALL_CONFIG_FILE = os.path.join(BASE_DIR, "config", "firewall", "firewall.json")
VLANS_CONFIG_FILE = os.path.join(BASE_DIR, "config", "vlans", "vlans.json")
WAN_CONFIG_FILE = os.path.join(BASE_DIR, "config", "wan", "wan.json")


# ==========================================
# Utility Functions
# ==========================================

def ensure_dirs():
    """Crear directorios necesarios para configuración y logs."""
    os.makedirs(os.path.dirname(FIREWALL_CONFIG_FILE), exist_ok=True)
    ioh.create_module_log_directory("firewall")
    ioh.ensure_module_config_directory("firewall")


def _run_command(cmd):
    """Alias para run_command."""
    return run_command(cmd)


# ==========================================
# Configuration Loading
# ==========================================

def load_firewall_config():
    """Load firewall configuration."""
    return load_json_config(FIREWALL_CONFIG_FILE, {
        "vlans": {}, 
        "wifi": {"isolated": True, "restricted": True},
        "status": 0
    })


def load_vlans_config():
    """Load VLANS configuration."""
    return load_json_config(VLANS_CONFIG_FILE, {"vlans": [], "status": 0})


def load_wan_config():
    """Load WAN configuration."""
    return load_json_config(WAN_CONFIG_FILE)


def save_firewall_config(data):
    """Save firewall configuration."""
    success = save_json_config(FIREWALL_CONFIG_FILE, data)
    if not success:
        logger.warning(f"No se pudo guardar la configuración de Firewall en {FIREWALL_CONFIG_FILE}")
    return success



# ==========================================
# Chain Management
# ==========================================

def ensure_fw_chains():
    """Crear y garantizar posición de las cadenas JSB de Firewall (L3)."""
    mh.ensure_global_chains()
    
    # 1. JSB_FW_STATS -> Hook to GLOBAL_STATS
    if not _run_command(["/usr/sbin/iptables", "-L", "JSB_FW_STATS", "-n"])[0]:
        _run_command(["/usr/sbin/iptables", "-N", "JSB_FW_STATS"])
    mh.ensure_module_hook("filter", "JSB_GLOBAL_STATS", "JSB_FW_STATS")

    # 2. JSB_FW_ISOLATE -> Hook to GLOBAL_ISOLATE
    if not _run_command(["/usr/sbin/iptables", "-L", "JSB_FW_ISOLATE", "-n"])[0]:
        _run_command(["/usr/sbin/iptables", "-N", "JSB_FW_ISOLATE"])
    mh.ensure_module_hook("filter", "JSB_GLOBAL_ISOLATE", "JSB_FW_ISOLATE")

    # 3. JSB_FW_RESTRICT -> Hook to GLOBAL_RESTRICT (on INPUT)
    if not _run_command(["/usr/sbin/iptables", "-L", "JSB_FW_RESTRICT", "-n"])[0]:
        _run_command(["/usr/sbin/iptables", "-N", "JSB_FW_RESTRICT"])
    mh.ensure_module_hook("filter", "JSB_GLOBAL_RESTRICT", "JSB_FW_RESTRICT")


def setup_wan_protection():
    """Configurar protección del router desde WAN (solo ICMP permitido)."""
    wan_cfg = load_wan_config()
    if not wan_cfg or not wan_cfg.get("interface"):
        return
    
    wan_interface = wan_cfg["interface"]
    
    # Limpiar cadena JSB_FW_RESTRICT
    _run_command(["/usr/sbin/iptables", "-F", "JSB_FW_RESTRICT"])
    
    # Permitir tráfico relacionado/establecido desde WAN
    _run_command([
        "/usr/sbin/iptables", "-A", "JSB_FW_RESTRICT", "-i", wan_interface,
        "-m", "conntrack", "--ctstate", "ESTABLISHED,RELATED", "-j", "RETURN"
    ])
   
    # Permitir ICMP desde WAN
    _run_command([
        "/usr/sbin/iptables", "-A", "JSB_FW_RESTRICT", "-i", wan_interface,
        "-p", "icmp", "-j", "RETURN"
    ])
   
    # Bloquear todo lo demás desde WAN
    _run_command([
        "/usr/sbin/iptables", "-A", "JSB_FW_RESTRICT", "-i", wan_interface, "-j", "DROP"
    ])
    
    logger.info(f"Protección WAN configurada en {wan_interface}")


# ==========================================
# VLAN Chain Management
# ==========================================

def create_input_vlan_chain(vlan_id: int, vlan_ip: str) -> bool:
    """Crear cadena INPUT_VLAN_X y vincularla desde INPUT."""
    chain_name = f"INPUT_VLAN_{vlan_id}"
    
    # Crear cadena
    success, output = _run_command(["/usr/sbin/iptables", "-N", chain_name])
    if not success and "already exists" not in output.lower():
        logger.error(f"Error creando {chain_name}: {output}")
        return False
    
    # Limpiar reglas existentes
    _run_command(["/usr/sbin/iptables", "-F", chain_name])
    
    # Vincular desde INPUT (después de JSB_FW_RESTRICT)
    # Verificar si ya está vinculada
    success, _ = _run_command([
        "/usr/sbin/iptables", "-C", "INPUT", "-s", vlan_ip, "-j", chain_name
    ])
    
    if not success:
        # No está vinculada, añadir después de JSB_FW_RESTRICT (posición 2)
        _run_command([
            "/usr/sbin/iptables", "-I", "INPUT", "2", "-s", vlan_ip, "-j", chain_name
        ])
        logger.info(f"{chain_name} vinculada desde INPUT")
    
    return True


def create_forward_vlan_chain(vlan_id: int, vlan_ip: str) -> bool:
    """Crear cadena FORWARD_VLAN_X y vincularla desde FORWARD."""
    chain_name = f"FORWARD_VLAN_{vlan_id}"
    
    # Crear cadena
    success, output = _run_command(["/usr/sbin/iptables", "-N", chain_name])
    if not success and "already exists" not in output.lower():
        logger.error(f"Error creando {chain_name}: {output}")
        return False
    
    # Limpiar reglas existentes
    _run_command(["/usr/sbin/iptables", "-F", chain_name])
    
    # Por defecto: RETURN (permitir que otros procedan)
    _run_command(["/usr/sbin/iptables", "-A", chain_name, "-j", "RETURN"])
   
    # Vincular desde FORWARD (después de JSB_FW_ISOLATE)
    # Verificar si ya está vinculada
    success, _ = _run_command([
        "/usr/sbin/iptables", "-C", "FORWARD", "-s", vlan_ip, "-j", chain_name
    ])
    
    if not success:
        # No está vinculada, añadir después de JSB_FW_ISOLATE (posición 2)
        _run_command([
            "/usr/sbin/iptables", "-I", "FORWARD", "2", "-s", vlan_ip, "-j", chain_name
        ])
        logger.info(f"{chain_name} vinculada desde FORWARD")
    
    return True


def remove_input_vlan_chain(vlan_id: int, vlan_ip: str):
    """Desvincular y eliminar cadena INPUT_VLAN_X."""
    chain_name = f"INPUT_VLAN_{vlan_id}"
    
    # Desvincular desde INPUT
    _run_command([
        "/usr/sbin/iptables", "-D", "INPUT", "-s", vlan_ip, "-j", chain_name
    ])
    
    # Limpiar y eliminar cadena
    _run_command(["/usr/sbin/iptables", "-F", chain_name])
    _run_command(["/usr/sbin/iptables", "-X", chain_name])
    
    logger.info(f"{chain_name} eliminada")


def remove_forward_vlan_chain(vlan_id: int, vlan_ip: str):
    """Desvincular y eliminar cadena FORWARD_VLAN_X."""
    chain_name = f"FORWARD_VLAN_{vlan_id}"
    
    # Desvincular desde FORWARD
    _run_command([
        "/usr/sbin/iptables", "-D", "FORWARD", "-s", vlan_ip, "-j", chain_name
    ])
    
    # Limpiar y eliminar cadena
    _run_command(["/usr/sbin/iptables", "-F", chain_name])
    _run_command(["/usr/sbin/iptables", "-X", chain_name])
    
    logger.info(f"{chain_name} eliminada")


# ==========================================
# Whitelist Management
# ==========================================

def apply_whitelist(vlan_id: int, whitelist: List[str]) -> Tuple[bool, str]:
    """Aplicar whitelist en cadena FORWARD_VLAN_X.
    
    Formatos soportados:
    - IP: 8.8.8.8
    - IP/proto: 8.8.8.8/tcp
    - IP:puerto: 192.168.1.1:80
    - IP:puerto/proto: 8.8.8.8:53/udp
    - :puerto: :443
    - :puerto/proto: :22/tcp
    """
    chain_name = f"FORWARD_VLAN_{vlan_id}"
    
    # FIX BUG #6: Preservar reglas DMZ ACCEPT antes de limpiar
    # Cargar dmz.json para identificar IPs DMZ reales
    dmz_ips = set()
    try:
        dmz_cfg_path = os.path.join(BASE_DIR, "config", "dmz", "dmz.json")
        if os.path.exists(dmz_cfg_path):
            with open(dmz_cfg_path, "r") as f:
                dmz_cfg = json.load(f)
                for dest in dmz_cfg.get("destinations", []):
                    dmz_ips.add(dest.get("ip"))
    except Exception as e:
        logger.warning(f"No se pudo cargar dmz.json: {e}")
    
    # Buscar reglas ACCEPT con IPs DMZ reales
    dmz_rules = []
    success, output = _run_command(["/usr/sbin/iptables", "-L", chain_name, "-n", "--line-numbers"])
    if success:
        for line in output.split('\n'):
            # Buscar reglas ACCEPT con destino específico usando regex
            if 'ACCEPT' in line:
                # Usar regex para extraer IP destino (más robusto que posiciones)
                # Patrón: buscar "ACCEPT" seguido de destino IP (no 0.0.0.0/0)
                match = re.search(r'\s+([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}(?:/\d+)?)\s+', line)
                if match:
                    dest_ip = match.group(1)
                    # Solo preservar si no es 0.0.0.0/0 y está en dmz_ips
                    if dest_ip != '0.0.0.0/0' and dest_ip in dmz_ips:
                        dmz_rules.append(dest_ip)
                        logger.info(f"Preservando regla DMZ ACCEPT para {dest_ip}")
    
    # Limpiar cadena
    _run_command(["/usr/sbin/iptables", "-F", chain_name])
    
    # Re-añadir reglas DMZ RETURN al inicio
    for dmz_ip in dmz_rules:
        _run_command(["/usr/sbin/iptables", "-A", chain_name, "-d", dmz_ip, "-j", "RETURN"])
        logger.info(f"Regla DMZ RETURN restaurada para {dmz_ip}")
   
    if not whitelist:
        # Sin reglas, DROP por defecto
        _run_command(["/usr/sbin/iptables", "-A", chain_name, "-j", "DROP"])
        return True, "Whitelist vacía, todo bloqueado"
    
    for rule in whitelist:
        success = apply_single_whitelist_rule(chain_name, rule)
        if not success:
            logger.warning(f"Error aplicando regla whitelist: {rule}")
    
    # DROP final para bloquear todo lo no permitido
    # Nota: No verificamos si existe porque apply_whitelist siempre hace FLUSH antes
    _run_command(["/usr/sbin/iptables", "-A", chain_name, "-j", "DROP"])
    logger.debug(f"Regla DROP añadida al final de {chain_name}")
    
    return True, f"Whitelist aplicada con {len(whitelist)} reglas"


def apply_single_whitelist_rule(chain_name: str, rule: str) -> bool:
    """Aplicar una regla de whitelist individual."""
    try:
        # Parsear regla: IP[:puerto][/proto]
        ip = None
        port = None
        protocol = None
        
        if "/" in rule:
            rule, protocol = rule.rsplit("/", 1)
        
        if ":" in rule:
            ip, port = rule.split(":", 1)
            if not ip:  # :puerto
                ip = None
        else:
            ip = rule if rule else None
        
        # Construir comandos para verificación y adición
        if port and protocol:
            # Caso: IP:puerto/proto o :puerto/proto
            check_cmd = ["/usr/sbin/iptables", "-C", chain_name]
            add_cmd = ["/usr/sbin/iptables", "-A", chain_name]
            
            if ip:
                check_cmd.extend(["-d", ip])
                add_cmd.extend(["-d", ip])
            
            check_cmd.extend(["-p", protocol, "--dport", port])
            add_cmd.extend(["-p", protocol, "--dport", port])
            
            # Usar RETURN en lugar de ACCEPT para permitir precedencia de otros módulos
            check_cmd.append("-j")
            check_cmd.append("RETURN")
            add_cmd.append("-j")
            add_cmd.append("RETURN")
           
            success, _ = _run_command(check_cmd)
            if not success:
                _run_command(add_cmd)
            
        elif port:
            # Caso: IP:puerto o :puerto (sin protocolo → TCP + UDP)
            for proto in ["tcp", "udp"]:
                check_cmd = ["/usr/sbin/iptables", "-C", chain_name]
                add_cmd = ["/usr/sbin/iptables", "-A", chain_name]
                
                if ip:
                    check_cmd.extend(["-d", ip])
                    add_cmd.extend(["-d", ip])
                
                check_cmd.extend(["-p", proto, "--dport", port, "-j", "ACCEPT"])
                add_cmd.extend(["-p", proto, "--dport", port, "-j", "ACCEPT"])
                
                success, _ = _run_command(check_cmd)
                if not success:
                    _run_command(add_cmd)
                    
        elif protocol and ip:
            # Caso: IP/proto (sin puerto)
            check_cmd = ["/usr/sbin/iptables", "-C", chain_name, "-d", ip, "-p", protocol, "-j", "ACCEPT"]
            add_cmd = ["/usr/sbin/iptables", "-A", chain_name, "-d", ip, "-p", protocol, "-j", "ACCEPT"]
            
            success, _ = _run_command(check_cmd)
            if not success:
                _run_command(add_cmd)

        elif protocol and not ip:
            # Caso: /proto (sin IP ni puerto)
            check_cmd = ["/usr/sbin/iptables", "-C", chain_name, "-p", protocol, "-j", "ACCEPT"]
            add_cmd = ["/usr/sbin/iptables", "-A", chain_name, "-p", protocol, "-j", "ACCEPT"]

            success, _ = _run_command(check_cmd)
            if not success:
                _run_command(add_cmd)
                
        elif ip:
            # Caso: solo IP (sin puerto ni protocolo)
            check_cmd = ["/usr/sbin/iptables", "-C", chain_name, "-d", ip, "-j", "ACCEPT"]
            add_cmd = ["/usr/sbin/iptables", "-A", chain_name, "-d", ip, "-j", "ACCEPT"]
            
            success, _ = _run_command(check_cmd)
            if not success:
                _run_command(add_cmd)
        else:
            # Caso: :puerto (sin IP ni protocolo, ya manejado arriba)
            logger.warning(f"Regla malformada: {rule}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error parseando regla whitelist '{rule}': {e}")
        return False

# ==========================================
# Captive Portal Management
# ==========================================

def setup_wifi_portal(portal_enabled: bool, portal_port: int, authorized_macs: List[str]):
    """Configura las reglas de iptables para el Portal Cautivo Wi-Fi."""
    wifi_cfg = mh.load_module_config(BASE_DIR, "wifi", {})
    wifi_iface = wifi_cfg.get("interface", "wlp3s0")
    wifi_ip = wifi_cfg.get("ip_address", "10.0.99.1")
    
    # 1. Limpiar reglas previas del portal (NAT y FILTER)
    # Tabla NAT
    _run_command(["/usr/sbin/iptables", "-t", "nat", "-F", "WIFI_PORTAL_REDIRECT"])
    _run_command(["/usr/sbin/iptables", "-t", "nat", "-X", "WIFI_PORTAL_REDIRECT"])
    
    # Tabla FILTER
    _run_command(["/usr/sbin/iptables", "-F", "WIFI_PORTAL_INPUT"])
    _run_command(["/usr/sbin/iptables", "-X", "WIFI_PORTAL_INPUT"])
    _run_command(["/usr/sbin/iptables", "-F", "WIFI_PORTAL_FORWARD"])
    _run_command(["/usr/sbin/iptables", "-X", "WIFI_PORTAL_FORWARD"])
    
    if not portal_enabled:
        # Desvincular si existen
        _run_command(["/usr/sbin/iptables", "-t", "nat", "-D", "PREROUTING", "-i", wifi_iface, "-p", "tcp", "--dport", "80", "-j", "WIFI_PORTAL_REDIRECT"])
        _run_command(["/usr/sbin/iptables", "-D", "INPUT", "-i", wifi_iface, "-j", "WIFI_PORTAL_INPUT"])
        _run_command(["/usr/sbin/iptables", "-D", "FORWARD", "-i", wifi_iface, "-j", "WIFI_PORTAL_FORWARD"])
        return True

    # 2. Crear Cadenas
    _run_command(["/usr/sbin/iptables", "-t", "nat", "-N", "WIFI_PORTAL_REDIRECT"])
    _run_command(["/usr/sbin/iptables", "-N", "WIFI_PORTAL_INPUT"])
    _run_command(["/usr/sbin/iptables", "-N", "WIFI_PORTAL_FORWARD"])

    # 3. Reglas de Bypass para MACs autorizadas
    for mac in authorized_macs:
        # En NAT: No redirigir
        _run_command(["/usr/sbin/iptables", "-t", "nat", "-A", "WIFI_PORTAL_REDIRECT", "-m", "mac", "--mac-source", mac, "-j", "RETURN"])
        # En FILTER: Saltar el bloqueo del portal
        _run_command(["/usr/sbin/iptables", "-A", "WIFI_PORTAL_INPUT", "-m", "mac", "--mac-source", mac, "-j", "RETURN"])
        _run_command(["/usr/sbin/iptables", "-A", "WIFI_PORTAL_FORWARD", "-m", "mac", "--mac-source", mac, "-j", "RETURN"])

    # 4. Reglas de Restricción para el resto
    
    # --- NAT: Redirigir HTTP (80) al portal local ---
    _run_command(["/usr/sbin/iptables", "-t", "nat", "-A", "WIFI_PORTAL_REDIRECT", "-p", "tcp", "--dport", "80", "-j", "DNAT", "--to-destination", f"{wifi_ip}:{portal_port}"])

    # --- FILTER (INPUT): Acceso al Router ---
    # Permitir DHCP, DNS y Acceso al Portal (Usamos RETURN para permitir que JSB_FW_RESTRICT aplique DROP si es necesario)
    _run_command(["/usr/sbin/iptables", "-A", "WIFI_PORTAL_INPUT", "-p", "udp", "--dport", "67:68", "-j", "RETURN"])
    _run_command(["/usr/sbin/iptables", "-A", "WIFI_PORTAL_INPUT", "-p", "udp", "--dport", "53", "-j", "RETURN"])
    _run_command(["/usr/sbin/iptables", "-A", "WIFI_PORTAL_INPUT", "-p", "tcp", "--dport", str(portal_port), "-j", "RETURN"])
    _run_command(["/usr/sbin/iptables", "-A", "WIFI_PORTAL_INPUT", "-p", "icmp", "-j", "RETURN"])
    
    # Bloquear el resto hacia el router desde el portal
    _run_command(["/usr/sbin/iptables", "-A", "WIFI_PORTAL_INPUT", "-p", "udp", "--dport", "21027", "-j", "ACCEPT"])
    _run_command(["/usr/sbin/iptables", "-A", "WIFI_PORTAL_INPUT", "-j", "DROP"])

    # --- FILTER (FORWARD): Acceso a Internet/Otras Redes ---
    # Permitir DNS hacia afuera (RETURN)
    _run_command(["/usr/sbin/iptables", "-A", "WIFI_PORTAL_FORWARD", "-p", "udp", "--dport", "53", "-j", "RETURN"])
    
    # REJECT HTTPS (443) y GCM (5228) para que el dispositivo no espere al timeout
    _run_command(["/usr/sbin/iptables", "-A", "WIFI_PORTAL_FORWARD", "-p", "tcp", "--match", "multiport", "--dports", "443,5228", "-j", "REJECT", "--reject-with", "tcp-reset"])
    
    # Bloquear todo lo demás en FORWARD mientras no esté autorizado
    _run_command(["/usr/sbin/iptables", "-A", "WIFI_PORTAL_FORWARD", "-j", "DROP"])

    # 5. Vincular Cadenas
    # NAT table
    success_nat, _ = _run_command(["/usr/sbin/iptables", "-t", "nat", "-C", "PREROUTING", "-i", wifi_iface, "-p", "tcp", "--dport", "80", "-j", "WIFI_PORTAL_REDIRECT"])
    if not success_nat:
        _run_command(["/usr/sbin/iptables", "-t", "nat", "-I", "PREROUTING", "1", "-i", wifi_iface, "-p", "tcp", "--dport", "80", "-j", "WIFI_PORTAL_REDIRECT"])

    # FILTER (INPUT): Posición 1 (antes de INPUT_WIFI y otras)
    _run_command(["/usr/sbin/iptables", "-D", "INPUT", "-i", wifi_iface, "-j", "WIFI_PORTAL_INPUT"])
    _run_command(["/usr/sbin/iptables", "-I", "INPUT", "1", "-i", wifi_iface, "-j", "WIFI_PORTAL_INPUT"])

    # FILTER (FORWARD): Posición 1 (Prioridad máxima para interceptar conexiones establecidas)
    _run_command(["/usr/sbin/iptables", "-D", "FORWARD", "-i", wifi_iface, "-j", "WIFI_PORTAL_FORWARD"])
    _run_command(["/usr/sbin/iptables", "-I", "FORWARD", "1", "-i", wifi_iface, "-j", "WIFI_PORTAL_FORWARD"])

    return True
