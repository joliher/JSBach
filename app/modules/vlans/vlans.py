# app/core/vlans.py

import os
import subprocess
import json
import ipaddress
from typing import Dict, Any, Tuple, Optional
from ...utils.global_helpers import module_helpers as mh, io_helpers as ioh
from ...utils.validators import validate_vlan_id, validate_ip_network
from .helpers import initialize_default_vlans, bridge_exists

# Config file in V4 structure
CONFIG_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "vlans", "vlans.json")
)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# Alias helpers para compatibilidad
_load_config = lambda: mh.load_json_config(CONFIG_FILE, {"vlans": [], "status": 0})
_save_config = lambda data: mh.save_json_config(CONFIG_FILE, data)
_update_status = lambda status: mh.update_module_status(CONFIG_FILE, status)
_run_cmd = lambda cmd, ignore_error=False: mh.run_command(cmd)

# Aliases para funciones de helpers (compatibilidad)
_initialize_default_vlans = lambda: initialize_default_vlans(CONFIG_FILE)
_bridge_exists = bridge_exists


# --------------------------------


# -----------------------------
# Acciones públicas (Admin API)
# -----------------------------


def start(params: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
    ioh.ensure_module_config_directory("vlans")
    ioh.create_module_log_directory("vlans")
    
    
    _initialize_default_vlans()
    
    # Verificar dependencias
    deps_ok, deps_msg = mh.check_module_dependencies(BASE_DIR, "vlans")
    if not deps_ok:
        return False, deps_msg
    
    cfg = _load_config()
    vlans = cfg.get("vlans", [])
    
    if not vlans:
        return False, "No hay VLANs configuradas"

    if _bridge_exists() and _vlans_already_started(vlans):
        return False, "VLANs ya iniciadas"
    
    created_bridge = False
    created_interfaces = []

    # Crear br0 si no existe
    if not _bridge_exists():
        success, msg = _run_cmd([f"{__import__('shutil').which('ip') or '/usr/sbin/ip'}", "link", "add", "name", "br0", "type", "bridge", "vlan_filtering", "1"], ignore_error=True)
        if not success:
            return False, f"Error creando bridge br0: {msg}"
        created_bridge = True
    
    success, msg = _run_cmd([f"{__import__('shutil').which('ip') or '/usr/sbin/ip'}", "link", "set", "br0", "up"])
    if not success:
        _rollback_start(created_bridge, created_interfaces)
        return False, f"Error habilitando bridge br0: {msg}"
    
    # --- PREPARAR JERARQUÍA DE FIREWALL ---
    mh.ensure_global_chains()
    _run_cmd([f"{__import__('shutil').which('iptables') or '/usr/sbin/iptables'}", "-N", "JSB_VLAN_STATS"], ignore_error=True)
    _run_cmd([f"{__import__('shutil').which('iptables') or '/usr/sbin/iptables'}", "-N", "JSB_VLAN_ISOLATE"], ignore_error=True)
    
    # Hook into Global Stats
    mh.ensure_module_hook("filter", "JSB_GLOBAL_STATS", "JSB_VLAN_STATS")

    # Hook into Global Isolate
    mh.ensure_module_hook("filter", "JSB_GLOBAL_ISOLATE", "JSB_VLAN_ISOLATE")
    
    # Crear subinterfaces VLAN y asignar IPs
    for vlan in vlans:
        vlan_id = str(vlan.get("id"))
        vlan_ip_interface = vlan.get("ip_interface")
        iface_name = f"br0.{vlan_id}"
        
        if not os.path.exists(f"/sys/class/net/{iface_name}"):
            _run_cmd([f"{__import__('shutil').which('ip') or '/usr/sbin/ip'}", "link", "add", "link", "br0", "name", iface_name, "type", "vlan", "id", vlan_id], ignore_error=True)
        
        _run_cmd([f"{__import__('shutil').which('ip') or '/usr/sbin/ip'}", "link", "set", iface_name, "up"])
        # Limpiar IPs antiguas para asegurar que solo la configurada esté presente
        _run_cmd([f"{__import__('shutil').which('ip') or '/usr/sbin/ip'}", "addr", "flush", "dev", iface_name], ignore_error=True)
        
        if vlan_ip_interface:
            _run_cmd([f"{__import__('shutil').which('ip') or '/usr/sbin/ip'}", "addr", "add", vlan_ip_interface, "dev", iface_name], ignore_error=True)

        # Reglas de conteo en la cadena de STATS (con RETURN)
        _run_cmd([f"{__import__('shutil').which('iptables') or '/usr/sbin/iptables'}", "-A", "JSB_VLAN_STATS", "-i", iface_name, "-j", "RETURN"])
        _run_cmd([f"{__import__('shutil').which('iptables') or '/usr/sbin/iptables'}", "-A", "JSB_VLAN_STATS", "-o", iface_name, "-j", "RETURN"])
    
    _update_status(1)
    return True, "VLANs iniciadas con jerarquía segura"


def stop(params: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
    ioh.ensure_module_config_directory("vlans")
    ioh.create_module_log_directory("vlans")
    
    # Cargar configuración para obtener las VLANs
    cfg = _load_config()
    vlans = cfg.get("vlans", [])
    
    # Limpiar integración con FORWARD
    _run_cmd([f"{__import__('shutil').which('iptables') or '/usr/sbin/iptables'}", "-D", "FORWARD", "-j", "JSB_VLAN_STATS"], ignore_error=True)
    _run_cmd([f"{__import__('shutil').which('iptables') or '/usr/sbin/iptables'}", "-D", "FORWARD", "-j", "JSB_VLAN_ISOLATE"], ignore_error=True)
    
    # Vaciar y eliminar cadenas
    _run_cmd([f"{__import__('shutil').which('iptables') or '/usr/sbin/iptables'}", "-F", "JSB_VLAN_STATS"], ignore_error=True)
    _run_cmd([f"{__import__('shutil').which('iptables') or '/usr/sbin/iptables'}", "-X", "JSB_VLAN_STATS"], ignore_error=True)
    _run_cmd([f"{__import__('shutil').which('iptables') or '/usr/sbin/iptables'}", "-F", "JSB_VLAN_ISOLATE"], ignore_error=True)
    _run_cmd([f"{__import__('shutil').which('iptables') or '/usr/sbin/iptables'}", "-X", "JSB_VLAN_ISOLATE"], ignore_error=True)

    # Limpiar logging inter-VLAN
    _run_cmd([f"{__import__('shutil').which('iptables') or '/usr/sbin/iptables'}", "-D", "FORWARD", "-i", "br0.+", "-o", "br0.+", "-j", "LOG", "--log-prefix", "[JSB-VLAN-INT] "], ignore_error=True)

    for vlan in vlans:
        vlan_id = str(vlan.get("id"))
        iface_name = f"br0.{vlan_id}"
        _run_cmd([f"{__import__('shutil').which('ip') or '/usr/sbin/ip'}", "link", "set", iface_name, "down"], ignore_error=True)
        _run_cmd([f"{__import__('shutil').which('ip') or '/usr/sbin/ip'}", "link", "del", "dev", iface_name], ignore_error=True)
    
    # Luego eliminar bridge
    if _bridge_exists():
        success, msg = _run_cmd([f"{__import__('shutil').which('ip') or '/usr/sbin/ip'}", "link", "set", "br0", "down"], ignore_error=True)
        if not success:
            return False, f"Error deteniendo bridge br0: {msg}"
        success, msg = _run_cmd([f"{__import__('shutil').which('ip') or '/usr/sbin/ip'}", "link", "del", "dev", "br0"], ignore_error=True)
        if not success:
            return False, f"Error eliminando bridge br0: {msg}"
    
    _update_status(0)
    return True, "VLANs detenidas"


def restart(params: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
    ok, msg = stop()
    if not ok:
        return False, msg
    return start()


def status(params: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
    ioh.ensure_module_config_directory("vlans")
    ioh.create_module_log_directory("vlans")
    _initialize_default_vlans()
    
    cfg = _load_config()
    vlans = cfg.get("vlans", [])
    
    # Verificar si el bridge br0 existe y está UP
    br0_exists = _bridge_exists()
    br0_is_up = False
    
    if br0_exists:
        try:
            result = subprocess.run(
                ["sudo", f"{__import__('shutil').which('ip') or '/usr/sbin/ip'}", "a", "show", "br0"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )
            br0_is_up = "state UP" in result.stdout
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass
    
    status_lines = ["Estado de VLANs:", "=" * 50]
    
    if not br0_exists:
        status_lines.append("🔴 Bridge br0: NO EXISTE")
        status_lines.append("\n⚠️ Las VLANs requieren que el bridge br0 esté creado")
        return True, "\n".join(status_lines)
    
    br0_status = "🟢 UP" if br0_is_up else "🔴 DOWN"
    status_lines.append(f"Bridge br0: {br0_status}")
    
    # Verificar cada VLAN configurada
    status_lines.append(f"\nVLANs configuradas: {len(vlans)}")
    status_lines.append("-" * 50)
    
    if vlans:
        for vlan in vlans:
            vlan_id = vlan.get('id')
            vlan_name = vlan.get('name', 'Sin nombre')
            ip_int = vlan.get('ip_interface', 'N/A')
            ip_net = vlan.get('ip_network', 'N/A')
            
            # Verificar si la subinterfaz br0.X existe y está UP
            subif_name = f"br0.{vlan_id}"
            try:
                result = subprocess.run(
                    ["sudo", f"{__import__('shutil').which('ip') or '/usr/sbin/ip'}", "a", "show", subif_name],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=5
                )
                is_up = "state UP" in result.stdout
                has_ip = f"inet {ip_int.split('/')[0]}" in result.stdout if '/' in ip_int else False
                subif_status = "🟢 UP" if is_up else "🔴 DOWN"
                ip_status = " ✅" if has_ip else " ⚠️ Sin IP"
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                subif_status = "❌ NO EXISTE"
                ip_status = ""
            
            status_lines.append(f"\nVLAN {vlan_id} ({vlan_name}):")
            status_lines.append(f"  Interfaz: {subif_name} [{subif_status}]{ip_status}")
            status_lines.append(f"  IP: {ip_int}")
            status_lines.append(f"  Red: {ip_net}")
    else:
        status_lines.append("\n(Sin VLANs configuradas)")
    
    return True, "\n".join(status_lines)


def config(params: Dict[str, Any]) -> Tuple[bool, str]:
    ioh.ensure_module_config_directory("vlans")
    ioh.create_module_log_directory("vlans")
    _initialize_default_vlans()
    
    # Validar parámetros
    if not params:
        return False, "Error: No se proporcionaron parámetros"
    
    if not isinstance(params, dict):
        return False, "Error: Los parámetros deben ser un diccionario"
    
    action = params.get("action")
    if not action:
        return False, "Falta parámetro 'action'"
    
    if not isinstance(action, str):
        return False, f"Error: 'action' debe ser una cadena, recibido: {type(action).__name__}"
    
    action = action.strip().lower()
    
    if not action:
        return False, "Error: 'action' no puede estar vacío"
    
    cfg = _load_config()
    
    if action == "add":
        required = ["id", "name"]
        for r in required:
            if r not in params:
                return False, f"Falta parámetro obligatorio '{r}'"
        
        # Validar id
        valid, error = validate_vlan_id(params["id"])
        if not valid:
            return False, f"Error: {error}"
        vlan_id = int(params["id"])
        
        # Validar name
        if not isinstance(params["name"], str):
            return False, f"Error: 'name' debe ser una cadena, recibido: {type(params['name']).__name__}"
        
        name = params["name"].strip()
        
        if not name:
            return False, "Error: 'name' no puede estar vacío"
        
        ip_interface = params.get("ip_interface", "").strip()
        ip_network = params.get("ip_network", "").strip()
        
        # Validar IP de interfaz si se proporciona
        if ip_interface:
            if not isinstance(ip_interface, str):
                return False, f"Error: 'ip_interface' debe ser una cadena, recibido: {type(ip_interface).__name__}"
            
            if '/' not in ip_interface:
                return False, "Error: la IP de interfaz debe incluir la máscara (ejemplo: 192.168.1.1/24)"
            
            try:
                ipaddress.IPv4Network(ip_interface, strict=False)
                
                # Validar que el último octeto no sea 0 ni 255
                ip_parts = ip_interface.split('/')[0].split('.')
                last_octet = int(ip_parts[3])
                
                if last_octet == 0 or last_octet == 255:
                    return False, "Error: la IP de interfaz no puede terminar en 0 o 255"
                
            except ValueError as e:
                return False, f"Error: formato de IP de interfaz inválido: {str(e)}"
        
        # Validar IP de red si se proporciona
        if ip_network:
            if not isinstance(ip_network, str):
                return False, f"Error: 'ip_network' debe ser una cadena, recibido: {type(ip_network).__name__}"
            
            if '/' not in ip_network:
                return False, "Error: la IP de red debe incluir la máscara (ejemplo: 192.168.1.0/24)"

            valid, error = validate_ip_network(ip_network)
            if not valid:
                return False, f"Error: {error}"
        
        # Validar que la IP de interfaz esté dentro de la red especificada
        if ip_interface and ip_network:
            try:
                ip_int_addr = ipaddress.IPv4Address(ip_interface.split('/')[0])
                network_obj = ipaddress.IPv4Network(ip_network, strict=False)
                
                if ip_int_addr not in network_obj:
                    return False, f"Error: la IP de interfaz {ip_interface.split('/')[0]} no está dentro de la red {ip_network}"
                
                # Validar que ambas tengan la misma máscara
                ip_int_mask = int(ip_interface.split('/')[1])
                ip_net_mask = int(ip_network.split('/')[1])
                
                if ip_int_mask != ip_net_mask:
                    return False, f"Error: la máscara de la IP de interfaz (/{ip_int_mask}) debe coincidir con la máscara de la red (/{ip_net_mask})"
                
            except (ValueError, IndexError) as e:
                return False, f"Error validando compatibilidad de IPs: {str(e)}"
        
        # Eliminar si ya existe (solo si no es VLAN protegida)
        cfg["vlans"] = [v for v in cfg["vlans"] if v.get("id") != vlan_id]
        # Agregar nueva
        cfg["vlans"].append({
            "id": vlan_id,
            "name": name,
            "ip_interface": ip_interface,
            "ip_network": ip_network
        })
        saved = _save_config(cfg)
        if not saved:
            return False, f"Error guardando configuración de VLANs en {CONFIG_FILE}"
        return True, f"VLAN {vlan_id} agregada"
    
    elif action == "remove":
        vlan_id = params.get("id")
        if not vlan_id:
            return False, "Falta parámetro 'id'"
        
        # Proteger VLANs 1 y 2
        if int(vlan_id) in [1, 2]:
            return False, f"VLAN {vlan_id} es protegida y no puede ser eliminada"
        
        original_count = len(cfg["vlans"])
        cfg["vlans"] = [v for v in cfg["vlans"] if str(v.get("id")) != str(vlan_id)]
        if len(cfg["vlans"]) == original_count:
            return False, f"VLAN {vlan_id} no encontrada"
        
        saved = _save_config(cfg)
        if not saved:
            return False, f"Error guardando configuración de VLANs en {CONFIG_FILE}"
        return True, f"VLAN {vlan_id} eliminada"
    
    elif action == "show":
        try:
            vlans = cfg.get("vlans", [])
            
            # Soporte para salida JSON (para frontend)
            if params.get("format") == "json":
                return True, json.dumps(vlans)
                
            if not vlans:
                return True, "No hay VLANs configuradas"
            
            result = "VLANs configuradas:\n"
            for vlan in vlans:
                ip_int = vlan.get('ip_interface', 'N/A')
                ip_net = vlan.get('ip_network', 'N/A')
                result += f"  ID: {vlan.get('id')}, Name: {vlan.get('name')}, IP Interfaz: {ip_int}, IP Red: {ip_net}\n"
            return True, result.rstrip()
        except Exception as e:
            return False, f"Error interno procesando solicitud: {str(e)}"
    
    else:
        return False, "Acción no válida. Use: add, remove, show"


def _rollback_start(created_bridge: bool, created_interfaces: list) -> None:
    for iface_name in created_interfaces:
        _run_cmd([f"{__import__('shutil').which('ip') or '/usr/sbin/ip'}", "link", "set", iface_name, "down"], ignore_error=True)
        _run_cmd([f"{__import__('shutil').which('ip') or '/usr/sbin/ip'}", "link", "del", "dev", iface_name], ignore_error=True)
    if created_bridge:
        _run_cmd([f"{__import__('shutil').which('ip') or '/usr/sbin/ip'}", "link", "set", "br0", "down"], ignore_error=True)
        _run_cmd([f"{__import__('shutil').which('ip') or '/usr/sbin/ip'}", "link", "del", "dev", "br0"], ignore_error=True)


def _interface_has_ip(interface: str, ip_interface: str) -> bool:
    if not ip_interface:
        return True
    try:
        ip_addr = ip_interface.split("/")[0]
        result = subprocess.run(
            [f"{__import__('shutil').which('ip') or '/usr/sbin/ip'}", "-4", "addr", "show", "dev", interface],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return f"inet {ip_addr}" in result.stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, IndexError):
        return False


def _vlans_already_started(vlans: list) -> bool:
    for vlan in vlans:
        vlan_id = str(vlan.get("id"))
        iface_name = f"br0.{vlan_id}"
        if not os.path.exists(f"/sys/class/net/{iface_name}"):
            return False
        if not _interface_has_ip(iface_name, vlan.get("ip_interface", "")):
            return False

    return True


def isolate(params: Dict[str, Any]) -> Tuple[bool, str]:
    vlan_id = params.get("vlan")
    if not vlan_id: return False, "Falta parámetro 'vlan'"
    iface = f"br0.{vlan_id}"
    # Bloquear en la sub-cadena dedicada JSB_VLAN_ISOLATE
    cmd = [f"{__import__('shutil').which('iptables') or '/usr/sbin/iptables'}", "-A", "JSB_VLAN_ISOLATE", "-i", iface, "-o", "br0.+", "-j", "DROP"]
    success, msg = _run_cmd(cmd)
    if not success: return False, f"Error aislando VLAN {vlan_id}: {msg}"
    _run_cmd([f"{__import__('shutil').which('iptables') or '/usr/sbin/iptables'}", "-A", "JSB_VLAN_ISOLATE", "-i", "br0.+", "-o", iface, "-j", "DROP"])
    return True, f"VLAN {vlan_id} aislada de otras VLANs"


def unisolate(params: Dict[str, Any]) -> Tuple[bool, str]:
    vlan_id = params.get("vlan")
    if not vlan_id: return False, "Falta parámetro 'vlan'"
    iface = f"br0.{vlan_id}"
    _run_cmd([f"{__import__('shutil').which('iptables') or '/usr/sbin/iptables'}", "-D", "JSB_VLAN_ISOLATE", "-i", iface, "-o", "br0.+", "-j", "DROP"])
    _run_cmd([f"{__import__('shutil').which('iptables') or '/usr/sbin/iptables'}", "-D", "JSB_VLAN_ISOLATE", "-i", "br0.+", "-o", iface, "-j", "DROP"])
    return True, f"VLAN {vlan_id} ya no está aislada"


def traffic_log(params: Dict[str, Any]) -> Tuple[bool, str]:
    status = params.get("status", "on")
    action = "-I" if status == "on" else "-D"
    cmd = [f"{__import__('shutil').which('iptables') or '/usr/sbin/iptables'}", action, "FORWARD", "1", "-i", "br0.+", "-o", "br0.+", "-j", "LOG", "--log-prefix", "[JSB-VLAN-INT] "]
    success, msg = _run_cmd(cmd)
    if status == "on" and not success: return False, f"Error activando log inter-VLAN: {msg}"
    return True, f"Log de tráfico inter-VLAN: {status}"


def top(params: Dict[str, Any] = None) -> Tuple[bool, str]:
    cfg = _load_config()
    vlans_list = cfg.get("vlans", [])
    if not vlans_list: return True, "No hay VLANs configuradas."
    res = "Consumo de Tráfico por VLAN (Estadísticas):\n==========================================\n"
    res += f"{'VLAN':<10} | {'Bytes IN':<15} | {'Bytes OUT':<15}\n" + "-" * 50 + "\n"
    
    # Obtener bytes de la sub-cadena JSB_VLAN_STATS
    success, output = _run_cmd([f"{__import__('shutil').which('iptables') or '/usr/sbin/iptables'}", "-L", "JSB_VLAN_STATS", "-v", "-n"])
    stats_data = {}
    if success:
        for line in output.strip().split('\n'):
            for vlan in vlans_list:
                v_id = str(vlan.get("id"))
                iface = f"br0.{v_id}"
                if iface in line:
                    parts = line.split()
                    bytes_val = parts[1]
                    if v_id not in stats_data: stats_data[v_id] = {"in": 0, "out": 0}
                    if f"-i {iface}" in line or f"{iface} *" in line:
                        stats_data[v_id]["in"] = bytes_val
                    elif f"-o {iface}" in line or f"* {iface}" in line:
                        stats_data[v_id]["out"] = bytes_val

    for vlan in vlans_list:
        v_id = str(vlan.get("id"))
        data = stats_data.get(v_id, {"in": 0, "out": 0})
        res += f"{v_id:<10} | {str(data['in']):<15} | {str(data['out']):<15}\n"
    return True, res


# -----------------------------
# Whitelist de acciones
# -----------------------------

ALLOWED_ACTIONS = {
    "start": start,
    "stop": stop,
    "restart": restart,
    "status": status,
    "config": config,
    "isolate": isolate,
    "unisolate": unisolate,
    "traffic_log": traffic_log,
    "top": top,
}