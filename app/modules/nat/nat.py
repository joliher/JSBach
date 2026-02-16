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
_run_command = lambda cmd: run_command(cmd)
_sanitize_interface_name = sanitize_interface_name  # Alias para compatibilidad


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
    if not _sanitize_interface_name(interfaz):
        return False, f"Nombre de interfaz inválido: '{interfaz}'. Solo use caracteres alfanuméricos, puntos, guiones y guiones bajos."

    # Comprobar si NAT ya está activo
    cmd = ["/usr/sbin/iptables", "-t", "nat", "-C", "POSTROUTING", "-o", interfaz, "-j", "MASQUERADE"]
    nat_rule_exists, _ = _run_command(cmd)

    # Capturar estado actual de IP forwarding para rollback
    success, output = _run_command(["/usr/sbin/sysctl", "-n", "net.ipv4.ip_forward"])
    ip_forward_prev = output.strip() if success else "0"

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
    nat_rule_status = "✅ Configurada" if nat_active else "❌ No configurada"
    
    overall_status = "🟢 ACTIVO" if (ip_forward == "1" and nat_active and is_up) else "🔴 INACTIVO"
    
    status_summary = f"""Estado de NAT:
==================
Estado general: {overall_status}
Interfaz: {interfaz} [{interface_status}]
IP Forwarding: {forwarding_status}
Regla MASQUERADE: {nat_rule_status}"""

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
    if not _sanitize_interface_name(interfaz):
        return False, f"Formato de interfaz inválido: '{interfaz}'. Debe ser alfanumérico y puede incluir '.' o '_'"
    
    # Verificar que la interfaz existe en el sistema
    success, output = _run_command(["/usr/sbin/ip", "link", "show", interfaz])
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


# -----------------------------
# Whitelist de acciones
# -----------------------------

ALLOWED_ACTIONS = {
    "start": start,
    "stop": stop,
    "restart": restart,
    "status": status,
    "config": config,
}