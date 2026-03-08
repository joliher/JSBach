# app/core/nat.py

import os
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
import json
from typing import Dict, Any, Tuple
from ...utils.global_helpers import module_helpers as mh, io_helpers as ioh
from ...utils.validators import sanitize_interface_name
from ...utils.global_helpers import (
    load_json_config, save_json_config, update_module_status, run_command
)

# Config file in V4 structure
CONFIG_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "nat", "nat.json")
)

# Alias helpers para compatibilidad
_load_config = lambda: load_json_config(CONFIG_FILE, {"interface": "", "status": 0})
_save_config = lambda config: save_json_config(CONFIG_FILE, config)
_update_status = lambda status: update_module_status(CONFIG_FILE, status)
_run_command = lambda cmd, ignore_error=False: run_command(cmd)



# -----------------------------
# Acciones públicas (Admin API)
# -----------------------------

def start(params: Dict[str, Any] = None) -> Tuple[bool, str]:
    ioh.ensure_module_config_directory("nat")
    ioh.create_module_log_directory("nat")
    config = _load_config()
    if not config:
        return False, "Configuración NAT no encontrada"

    if mh.get_module_status_by_name(BASE_DIR, "wan") != 1:
        return False, "El módulo WAN debe estar activo para iniciar NAT"

    interfaz = config.get("interface")
    if not interfaz:
        return False, "Interfaz NAT no definida"
    
    # Validar nombre de interfaz seguro
    if not sanitize_interface_name(interfaz):
        return False, f"Nombre de interfaz inválido: '{interfaz}'. Solo use caracteres alfanuméricos, puntos, guiones y guiones bajos."

    # Comprobar si NAT ya está activo
    cmd = ["/usr/sbin/iptables", "-t", "nat", "-C", "POSTROUTING", "-o", interfaz, "-j", "MASQUERADE"]
    nat_rule_exists, _ = _run_command(cmd)

    # Capturar estado actual de IP forwarding para rollback
    success, output = _run_command(["/usr/sbin/sysctl", "-n", "net.ipv4.ip_forward"])
    ip_forward_prev = output.strip() if success else "0"

    # --- PREPARAR JERARQUÍA DE FIREWALL (Search & Destroy) ---
    mh.ensure_global_chains()
    _run_command(["/usr/sbin/iptables", "-t", "nat", "-N", "JSB_NAT_STATS"], ignore_error=True)
    _run_command(["/usr/sbin/iptables", "-t", "filter", "-N", "JSB_NAT_ISOLATE"], ignore_error=True)
    
    # Hook into Global Isolate (FORWARD)
    mh.ensure_module_hook("filter", "JSB_GLOBAL_ISOLATE", "JSB_NAT_ISOLATE")
    
    # Hook into Global NAT (POSTROUTING)
    if not _run_command(["/usr/sbin/iptables", "-t", "nat", "-C", "JSB_GLOBAL_NAT", "-j", "JSB_NAT_STATS"])[0]:
        _run_command(["/usr/sbin/iptables", "-t", "nat", "-A", "JSB_GLOBAL_NAT", "-j", "JSB_NAT_STATS"])
    
    # Asegurar RETURN al final de la cadena de estadísticas
    if not _run_command(["/usr/sbin/iptables", "-t", "nat", "-C", "JSB_NAT_STATS", "-j", "RETURN"])[0]:
        _run_command(["/usr/sbin/iptables", "-t", "nat", "-A", "JSB_NAT_STATS", "-j", "RETURN"])
    
    if nat_rule_exists and ip_forward_prev == "1":
        return True, f"NAT ya activado en {interfaz}"

    # Activar IP forwarding usando sysctl
    success, msg = _run_command(["/usr/sbin/sysctl", "-w", "net.ipv4.ip_forward=1"])
    if not success:
        return False, f"Error activando IP forwarding: {msg}"
    
    # Añadir regla NAT
    if not nat_rule_exists:
        success, msg = _run_command(["/usr/sbin/iptables", "-t", "nat", "-A", "POSTROUTING", "-o", interfaz, "-j", "MASQUERADE"])
        if not success:
            # Rollback ip_forward al estado anterior
            if ip_forward_prev in ("0", "1"):
                _run_command(["/usr/sbin/sysctl", "-w", f"net.ipv4.ip_forward={ip_forward_prev}"])
            return False, f"Error añadiendo regla NAT: {msg}"
    
    _update_status(1)
    return True, f"NAT activado en {interfaz}"


def stop(params: Dict[str, Any] = None) -> Tuple[bool, str]:
    ioh.ensure_module_config_directory("nat")
    ioh.create_module_log_directory("nat")
    config = _load_config()
    if not config:
        return False, "Configuración NAT no encontrada"

    interfaz = config.get("interface")
    if not interfaz:
        return False, "Interfaz NAT no definida"

    # Limpiar integración con FORWARD y POSTROUTING
    _run_command(["/usr/sbin/iptables", "-D", "FORWARD", "-j", "JSB_NAT_ISOLATE"], ignore_error=True)
    _run_command(["/usr/sbin/iptables", "-t", "nat", "-D", "POSTROUTING", "-o", interfaz, "-j", "JSB_NAT_STATS"], ignore_error=True)
    
    # Vaciar y eliminar cadenas
    _run_command(["/usr/sbin/iptables", "-t", "nat", "-F", "JSB_NAT_STATS"], ignore_error=True)
    _run_command(["/usr/sbin/iptables", "-t", "nat", "-X", "JSB_NAT_STATS"], ignore_error=True)
    _run_command(["/usr/sbin/iptables", "-F", "JSB_NAT_ISOLATE"], ignore_error=True)
    _run_command(["/usr/sbin/iptables", "-X", "JSB_NAT_ISOLATE"], ignore_error=True)

    # Limpiar logging
    _run_command(["/usr/sbin/iptables", "-t", "nat", "-D", "POSTROUTING", "-o", interfaz, "-j", "LOG", "--log-prefix", "[JSB-NAT-OUT] "], ignore_error=True)

    # Verificar si otros módulos dependen del IP forwarding
    base_config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "config"))
    modules_to_check = {
        "firewall": os.path.join(base_config_dir, "firewall", "firewall.json"),
        "dmz": os.path.join(base_config_dir, "dmz", "dmz.json")
    }
    
    active_modules = []
    for module_name, config_path in modules_to_check.items():
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    module_config = json.load(f)
                    if module_config.get("status") == 1:
                        active_modules.append(module_name)
            except Exception:
                # Si hay error leyendo, asumir activo para evitar desactivar forwarding
                active_modules.append(f"{module_name} (config ilegible)")
    
    if active_modules:
        modules_str = ", ".join(active_modules)
        return False, f"No se puede desactivar IP forwarding: los módulos [{modules_str}] están activos y lo requieren. Detén primero esos módulos."

    # Desactivar IP forwarding usando sysctl
    success, msg = _run_command(["/usr/sbin/sysctl", "-w", "net.ipv4.ip_forward=0"])
    if not success:
        return False, f"Error desactivando IP forwarding: {msg}"
    
    # Eliminar regla NAT (no importa si falla, puede que no exista)
    _run_command(["/usr/sbin/iptables", "-t", "nat", "-D", "POSTROUTING", "-o", interfaz, "-j", "MASQUERADE"])
    
    _update_status(0)
    return True, f"NAT desactivado en {interfaz}"


def restart(params: Dict[str, Any] = None) -> Tuple[bool, str]:
    ok, msg = stop()
    if not ok:
        return False, msg
    return start()


def status(params: Dict[str, Any] = None) -> Tuple[bool, str]:
    ioh.ensure_module_config_directory("nat")
    ioh.create_module_log_directory("nat")
    config = _load_config()
    if not config:
        return False, "Configuración NAT no encontrada"

    interfaz = config.get("interface")
    if not interfaz:
        return False, "Interfaz NAT no definida"

    # Verificar si la interfaz existe y está UP
    success, ip_info = _run_command(["/usr/sbin/ip", "a", "show", interfaz])
    if not success:
        return False, f"La interfaz {interfaz} no existe"
    
    is_up = "state UP" in ip_info or ",UP," in ip_info
    interface_status = "🟢 UP" if is_up else "🔴 DOWN"

    # Verificar IP forwarding
    success, output = _run_command(["/usr/sbin/sysctl", "-n", "net.ipv4.ip_forward"])
    if not success:
        return False, f"Error verificando NAT: {output}"
    
    ip_forward = output.strip()
    forwarding_status = "✅ Activado" if ip_forward == "1" else "❌ Desactivado"
    
    # Verificar regla NAT
    cmd = ["/usr/sbin/iptables", "-t", "nat", "-C", "POSTROUTING", "-o", interfaz, "-j", "MASQUERADE"]
    nat_active, _ = _run_command(cmd)
    
    overall_status = "🟢 ACTIVO" if (ip_forward == "1" and nat_active and is_up) else "🔴 INACTIVO"
    
    # Verificar si hay logging activo
    log_cmd = ["/usr/sbin/iptables", "-t", "nat", "-C", "POSTROUTING", "-o", interfaz, "-j", "LOG", "--log-prefix", "[JSB-NAT-OUT] "]
    log_active, _ = _run_command(log_cmd)
    
    status_summary = f"""Estado de NAT:
==================
Estado general: {overall_status}
Interfaz: {interfaz} [{interface_status}]
IP Forwarding: {forwarding_status}
Regla MASQUERADE: {"✅ Configurada" if nat_active else "❌ No configurada"}
Registro tráfico: {"✅ Activado" if log_active else "❌ Desactivado"}"""

    if ip_forward == "1" and not nat_active:
        status_summary += "\n\n⚠️ Aviso: IP forwarding está activo, pero NAT no está configurado"

    if not is_up:
        status_summary += f"\n\n⚠️ ADVERTENCIA: La interfaz {interfaz} está DOWN (inactiva)"
    
    return True, status_summary


def config(params: Dict[str, Any]) -> Tuple[bool, str]:
    ioh.ensure_module_config_directory("nat")
    ioh.create_module_log_directory("nat")
    
    # Validar parámetros
    if not params:
        return False, "No se proporcionaron parámetros"
    
    if not isinstance(params, dict):
        return False, "Los parámetros deben ser un diccionario"
    
    interfaz = params.get("interface")
    
    # Validar interface (requerido)
    if not interfaz:
        return False, "Falta parámetro obligatorio 'interface'"
    
    if not isinstance(interfaz, str):
        return False, "El parámetro 'interface' debe ser una cadena de texto"
    
    interfaz = interfaz.strip()
    if not interfaz:
        return False, "El parámetro 'interface' no puede estar vacío"
    
    # Validar formato de interfaz
    if not sanitize_interface_name(interfaz):
        return False, f"Formato de interfaz inválido: '{interfaz}'. Debe ser alfanumérico y puede incluir '.' o '_'"
    
    # Verificar que la interfaz existe en el sistema
    success, _ = _run_command(["/usr/sbin/ip", "link", "show", interfaz])
    if not success:
        return False, f"La interfaz '{interfaz}' no existe en el sistema"

    # Cargar configuración existente para preservar el status
    existing_cfg = _load_config() or {}
    existing_cfg["interface"] = interfaz
    if "status" not in existing_cfg:
        existing_cfg["status"] = 0
    
    saved = _save_config(existing_cfg)
    if not saved:
        return False, f"Error guardando configuración NAT en {CONFIG_FILE}"
    return True, f"Configuración NAT guardada: interfaz {interfaz}"


def block(params: Dict[str, Any]) -> Tuple[bool, str]:
    ip = params.get("ip")
    if not ip: return False, "Falta parámetro 'ip'"
    
    # Bloquear en la sub-cadena dedicada JSB_NAT_ISOLATE
    cmd = ["/usr/sbin/iptables", "-A", "JSB_NAT_ISOLATE", "-s", ip, "-j", "DROP"]
    success, msg = _run_command(cmd)
    if not success: return False, f"Error bloqueando IP {ip}: {msg}"
    
    # Limpiar sesiones conntrack
    _run_command(["/usr/sbin/conntrack", "-D", "-s", ip])
    
    return True, f"IP {ip} bloqueada para salida (NAT)"


def unblock(params: Dict[str, Any]) -> Tuple[bool, str]:
    ip = params.get("ip")
    if not ip: return False, "Falta parámetro 'ip'"
    
    cmd = ["/usr/sbin/iptables", "-D", "JSB_NAT_ISOLATE", "-s", ip, "-j", "DROP"]
    success, msg = _run_command(cmd)
    if not success: return False, f"Error desbloqueando IP {ip}: {msg}"
    return True, f"IP {ip} desbloqueada"


def traffic_log(params: Dict[str, Any]) -> Tuple[bool, str]:
    status = params.get("status", "on")
    config = _load_config()
    interfaz = config.get("interface", "")
    
    action = "-I" if status == "on" else "-D"
    cmd = ["/usr/sbin/iptables", "-t", "nat", action, "POSTROUTING", "1", "-o", interfaz, "-j", "LOG", "--log-prefix", "[JSB-NAT-OUT] "]
    
    success, msg = _run_command(cmd)
    if status == "on" and not success:
        return False, f"Error activando log de NAT: {msg}"
    
    return True, f"Log de tráfico NAT: {status}"


def top(params: Dict[str, Any] = None) -> Tuple[bool, str]:
    """Muestra conexiones NAT activas agrupadas por IP origen usando conntrack"""
    success, output = _run_command(["/usr/sbin/conntrack", "-L"])
    if not success:
        return True, "No se pudo obtener información de conntrack."

    sessions = {}
    lines = output.strip().split('\n')
    for line in lines:
        if "src=" in line:
            parts = line.split()
            src_ip = None
            for p in parts:
                if p.startswith("src="):
                    src_ip = p.split('=')[1]
                    break
            if src_ip:
                sessions[src_ip] = sessions.get(src_ip, 0) + 1
    
    if not sessions:
        return True, "No hay sesiones NAT activas registradas."

    sorted_sessions = sorted(sessions.items(), key=lambda x: x[1], reverse=True)[:10]
    
    res = "Top 10 Consumidores NAT (Sesiones activas):\n"
    res += "========================================\n"
    for ip, count in sorted_sessions:
        res += f"IP: {ip:<15} | Sesiones: {count}\n"
    
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
    "block": block,
    "unblock": unblock,
    "traffic_log": traffic_log,
    "top": top,
}