# app/core/module_helpers.py
"""
Funciones auxiliares comunes para todos los módulos core.
Centraliza: config I/O, status management, command execution, validación de interfaces.
"""

import subprocess
import json
import os
import fcntl
import re
import logging
from typing import Dict, Any, Tuple, Optional

# Configurar logging
logger = logging.getLogger(__name__)


# =============================================================================
# GESTIÓN DE CONFIGURACIÓN (Config I/O)
# =============================================================================

def load_json_config(file_path: str, default_value: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Cargar configuración JSON desde archivo.
    
    Args:
        file_path: Ruta al archivo JSON
        default_value: Valor por defecto si no existe o está vacío
    
    Returns:
        Dict con la configuración cargada
    """
    if default_value is None:
        default_value = {}
    
    if not os.path.exists(file_path):
        return default_value
    
    try:
        with open(file_path, "r") as f:
            content = f.read().strip()
            if not content:
                return default_value
            loaded_data = json.loads(content)
            # Combinar con valores por defecto para asegurar que todas las claves existan
            result = default_value.copy()
            result.update(loaded_data)
            return result
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Error cargando configuración de {file_path}: {e}")
        return default_value


def save_json_config(file_path: str, data: Dict[str, Any]) -> bool:
    """
    Guardar configuración JSON en archivo con lock exclusivo.
    
    Args:
        file_path: Ruta al archivo JSON
        data: Dict a guardar
    
    Returns:
        True si se guardó exitosamente, False en caso contrario
    """
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            json.dump(data, f, indent=4)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        logger.info(f"Configuración guardada en {file_path}")
        return True
    except Exception as e:
        logger.error(f"Error guardando configuración en {file_path}: {e}")
        return False


# =============================================================================
# GESTIÓN DE STATUS
# =============================================================================

def update_module_status(file_path: str, status: int) -> bool:
    """
    Actualizar el status de un módulo en su archivo de configuración.
    
    Args:
        file_path: Ruta al archivo de configuración JSON
        status: 0=inactivo, 1=activo
    
    Returns:
        True si se actualizó exitosamente
    """
    cfg = load_json_config(file_path, {})
    cfg["status"] = status
    return save_json_config(file_path, cfg)


def get_module_status(file_path: str) -> int:
    """
    Obtener el status actual de un módulo desde su path de config.
    
    Args:
        file_path: Ruta al archivo de configuración JSON
    
    Returns:
        0 si inactivo, 1 si activo, -1 si no existe o error
    """
    try:
        cfg = load_json_config(file_path, {})
        return cfg.get("status", 0) # Default to 0 instead of -1 if key missing
    except Exception:
        return 0

def get_module_status_by_name(base_dir: str, module_name: str) -> int:
    """Obtener status de módulo por su nombre."""
    path = get_config_file_path(base_dir, module_name)
    return get_module_status(path)


# =============================================================================
# EJECUCIÓN DE COMANDOS
# =============================================================================

def run_command(cmd: list, use_sudo: bool = True, timeout: int = 30, ignore_error: bool = False) -> Tuple[bool, str]:
    """
    Ejecutar comando shell con opciones de sudo y timeout.
    
    Args:
        cmd: Lista de componentes del comando
        use_sudo: Si True, antepone 'sudo'
        timeout: Timeout en segundos
    
    Returns:
        Tuple[success, output/error_message]
    """
    try:
        full_cmd = (["sudo"] + cmd) if use_sudo else cmd
        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False
        )
        
        if result.returncode == 0:
            return True, result.stdout.strip()
        else:
            error_msg = result.stderr.strip() or "Comando falló sin mensaje de error"
            return False, error_msg
    
    except subprocess.TimeoutExpired:
        return False, f"Timeout ejecutando comando (>{timeout}s)"
    except Exception as e:
        return False, f"Error ejecutando comando: {str(e)}"


# =============================================================================
# GESTIÓN GLOBAL DE FIREWALL (Anchor Chains)
# =============================================================================

GLOBAL_MODULE_ORDER = ["wan", "vlans", "wifi", "tagging", "firewall", "dmz", "nat", "dhcp"]

def ensure_chain_at_position(table: str, parent: str, target: str, position: int) -> bool:
    """Asegura que una cadena objetivo esté en una posición específica de la cadena padre."""
    run_command(["iptables", "-t", table, "-N", target])
    
    # 2. Verificar posición actual
    success, output = run_command(["iptables", "-t", table, "-L", parent, "-n", "--line-numbers"])
    if not success:
        return False

    current_pos = None
    for line in output.split('\n'):
        if target in line:
            # Match line number
            match = re.match(r'^\s*(\d+)\s+', line.strip())
            if match:
                # Double check it is the right target
                if f" {target} " in f" {line} ":
                    current_pos = int(match.group(1))
                    break

    if current_pos == position:
        return True

    # 3. Reposicionar
    if current_pos is not None:
        run_command(["iptables", "-t", table, "-D", parent, "-j", target])
    
    success, _ = run_command(["iptables", "-t", table, "-I", parent, str(position), "-j", target])
    return success


def ensure_global_chains():
    """Establece la jerarquía global de JSBach en las tablas de firewall."""
    # FORWARD Hierarchy
    ensure_chain_at_position("filter", "FORWARD", "JSB_GLOBAL_STATS", 1)
    ensure_chain_at_position("filter", "FORWARD", "JSB_GLOBAL_ISOLATE", 2)
    
    # INPUT Hierarchy
    ensure_chain_at_position("filter", "INPUT", "JSB_GLOBAL_RESTRICT", 1)
    
    # NAT Hierarchy
    ensure_chain_at_position("nat", "PREROUTING", "JSB_GLOBAL_PRE", 1)
    ensure_chain_at_position("nat", "POSTROUTING", "JSB_GLOBAL_NAT", 1)


def ensure_ebtables_global_chains() -> None:
    """Garantiza la jerarquía global de ebtables."""
    # Tabla filter (por defecto en ebtables)
    # JSB_GLOBAL_EBT_STATS en posición 1 de FORWARD
    run_command(["ebtables", "-N", "JSB_GLOBAL_EBT_STATS"], ignore_error=True)
    
    # Verificar posición en FORWARD
    ebt_list_cmd = ["ebtables", "-L", "FORWARD", "--Ln"]
    success, output = run_command(ebt_list_cmd)
    if success:
        if "JSB_GLOBAL_EBT_STATS" not in output:
            run_command(["ebtables", "-I", "FORWARD", "1", "-j", "JSB_GLOBAL_EBT_STATS"])
        else:
            # Simple check, if not 1, move it
            if "1 JSB_GLOBAL_EBT_STATS" not in output:
                run_command(["ebtables", "-D", "FORWARD", "-j", "JSB_GLOBAL_EBT_STATS"], ignore_error=True)
                run_command(["ebtables", "-I", "FORWARD", "1", "-j", "JSB_GLOBAL_EBT_STATS"])

    # JSB_GLOBAL_EBT_ISOLATE en posición 2 de FORWARD
    run_command(["ebtables", "-N", "JSB_GLOBAL_EBT_ISOLATE"], ignore_error=True)
    if "JSB_GLOBAL_EBT_ISOLATE" not in output:
        run_command(["ebtables", "-I", "FORWARD", "2", "-j", "JSB_GLOBAL_EBT_ISOLATE"])
    else:
        # Check if it is at position 2
        if "2 JSB_GLOBAL_EBT_ISOLATE" not in output:
            run_command(["ebtables", "-D", "FORWARD", "-j", "JSB_GLOBAL_EBT_ISOLATE"], ignore_error=True)
            run_command(["ebtables", "-I", "FORWARD", "2", "-j", "JSB_GLOBAL_EBT_ISOLATE"])


def ensure_module_hook(table: str, global_chain: str, module_chain: str, binary: str = "iptables", extra_args: list = None) -> bool:
    """
    Asegura que una cadena de módulo esté en la posición correcta dentro de una cadena global.
    Permite argumentos extra (ej: -i eth0) para el filtrado previo al salto.
    """
    cmd_base = [f"/usr/sbin/{binary}"]
    if extra_args is None:
        extra_args = []
        
    # 1. Asegurar que las cadenas existen
    run_command(cmd_base + ["-t", table, "-N", global_chain])
    run_command(cmd_base + ["-t", table, "-N", module_chain])

    # 2. Identificar qué módulo es
    module_name = None
    for m in GLOBAL_MODULE_ORDER:
        if m.upper() in module_chain.upper():
            module_name = m
            break
    
    # (Buscamos coincidencias de la cadena destino)
    list_cmd = cmd_base + ["-t", table, "-L", global_chain, "--line-numbers"]
    if binary == "iptables":
        # Solo iptables soporta -n de forma fiable para evitar resolución DNS
        list_cmd.insert(-1, "-n")
        
    success, output = run_command(list_cmd)
    if success:
        # Borrar de abajo a arriba para no alterar números de línea durante el proceso
        lines = output.split('\n')
        for line in reversed(lines):
            if module_chain in line:
                match = re.match(r'^\s*(\d+)\s+', line.strip())
                if match:
                    line_num = match.group(1)
                    # For ebtables, -D requires the full rule, not just line number
                    if binary == "ebtables":
                        # Attempt to reconstruct the rule for ebtables -D
                        # This is a simplification and might not cover all cases
                        rule_parts = line.split()
                        try:
                            # Find -j and the target chain
                            j_idx = rule_parts.index("-j")
                            target_idx = j_idx + 1
                            if target_idx < len(rule_parts) and rule_parts[target_idx] == module_chain:
                                # Remove line number and target chain from rule_parts
                                rule_to_delete = [p for i, p in enumerate(rule_parts) if i != 0 and i != target_idx]
                                run_command(cmd_base + ["-t", table, "-D", global_chain] + rule_to_delete)
                        except ValueError:
                            # -j not found, try deleting by line number if it's a simple jump
                            run_command(cmd_base + ["-t", table, "-D", global_chain, line_num])
                    else: # iptables can use line number
                        run_command(cmd_base + ["-t", table, "-D", global_chain, line_num])

    if not module_name:
        # Si no se reconoce el módulo, simplemente añadir al final con los argumentos extra
        return run_command(cmd_base + ["-t", table, "-A", global_chain] + extra_args + ["-j", module_chain])[0]

    # 4. Obtener hooks actuales (módulos) en la cadena global para calcular posición
    success, output = run_command(cmd_base + ["-t", table, "-L", global_chain, "-n"])
    current_hooks = []
    if success:
        for line in output.split('\n'):
            for m in GLOBAL_MODULE_ORDER:
                # Reconocer hook si contiene el nombre del módulo Y (tiene prefijo JSB_ O es una de las cadenas conocidas)
                # O si la cadena destino (module_chain) está presente.
                if m.upper() in line.upper() and ("JSB_" in line.upper() or "WIFI" in line.upper()) and "-j" in line:
                    current_hooks.append(m)
                    break
    
    # 5. Determinar posición de inserción
    # Queremos insertar después de todos los módulos que van antes en GLOBAL_MODULE_ORDER
    my_idx = GLOBAL_MODULE_ORDER.index(module_name)
    pos = 1
    for m in current_hooks:
        if GLOBAL_MODULE_ORDER.index(m) < my_idx:
            pos += 1
    
    # 6. Insertar regla
    success, output = run_command(cmd_base + ["-t", table, "-I", global_chain, str(pos)] + extra_args + ["-j", module_chain])
    if success:
        logger.info(f"Hook {module_chain} insertado en {global_chain} (pos {pos}) {'con extra_args' if extra_args else ''}")
    else:
        logger.error(f"Error insertando hook {module_chain} en {global_chain}: {output}")
        
    return success


# =============================================================================
# VALIDACIÓN DE INTERFACES
# =============================================================================

def validate_interface_name(name: str) -> bool:
    """
    Validar que el nombre de interfaz sea seguro.
    Solo permite: alfanuméricos, puntos, guiones, guiones bajos.
    
    Args:
        name: Nombre de la interfaz a validar
    
    Returns:
        True si es válido, False en caso contrario
    """
    if not name or not isinstance(name, str):
        return False
    return bool(re.match(r'^[a-zA-Z0-9._-]+$', name))


def interface_exists(iface_name: str) -> bool:
    """
    Verificar si una interfaz existe en el sistema.
    
    Args:
        iface_name: Nombre de la interfaz
    
    Returns:
        True si existe, False en caso contrario
    """
    success, output = run_command(["ip", "link", "show", iface_name], use_sudo=False)
    return success


# =============================================================================
# CARGAR CONFIGURACIÓN DE OTROS MÓDULOS
# =============================================================================

def load_module_config(base_dir: str, module_name: str, default: Dict = None) -> Dict[str, Any]:
    """
    Cargar configuración de otro módulo.
    
    Args:
        base_dir: Directorio base del proyecto
        module_name: Nombre del módulo (ej: "wan", "vlans", etc)
        default: Valor por defecto si no existe
    
    Returns:
        Dict con la configuración
    """
    if default is None:
        default = {}
    
    config_file = os.path.join(base_dir, "config", module_name, f"{module_name}.json")
    return load_json_config(config_file, default)


def get_wan_interface(base_dir: str) -> Optional[str]:
    """
    Obtener la interfaz WAN configurada.
    
    Args:
        base_dir: Directorio base del proyecto
    
    Returns:
        Nombre de la interfaz o None si no está configurada
    """
    wan_cfg = load_module_config(base_dir, "wan", {})
    return wan_cfg.get("interface")


# =============================================================================
# UTILIDADES PARA DIRECTORIOS
# =============================================================================

def ensure_module_dirs(base_dir: str, module_name: str) -> None:
    """
    Asegurar que existan los directorios de config y logs para un módulo.
    
    Args:
        base_dir: Directorio base del proyecto
        module_name: Nombre del módulo
    """
    config_dir = os.path.join(base_dir, "config", module_name)
    log_dir = os.path.join(base_dir, "logs", module_name)
    
    os.makedirs(config_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)


def get_config_file_path(base_dir: str, module_name: str) -> str:
    """
    Obtener la ruta del archivo de configuración de un módulo.
    
    Args:
        base_dir: Directorio base del proyecto
        module_name: Nombre del módulo
    
    Returns:
        Ruta completa al archivo JSON de configuración
    """
    return os.path.join(base_dir, "config", module_name, f"{module_name}.json")


def get_log_file_path(base_dir: str, module_name: str) -> str:
    """
    Obtener la ruta del archivo de log de un módulo.
    
    Args:
        base_dir: Directorio base del proyecto
        module_name: Nombre del módulo
    
    Returns:
        Ruta completa al archivo de log
    """
    return os.path.join(base_dir, "logs", module_name, "actions.log")

def check_module_dependencies(base_dir: str, module_name: str = None) -> Tuple[bool, str]:
    """
    Verifica dependencias jerárquicas de un módulo.
    Jerarquía: WAN -> VLANs -> Tagging -> [Firewall, Ebtables, DMZ]
    DMZ requiere Firewall adicionalmente.
    """
    if module_name is None:
        return True, "Dependencias satisfechas"

    # 0. WAN y Wi-Fi no tienen dependencias externas de arranque
    if module_name in ["wan", "wifi"]:
        return True, "Dependencias satisfechas"

    # 1. Tagging depende solo de VLANs
    if module_name == "tagging":
        if get_module_status_by_name(base_dir, "vlans") != 1:
            return False, "Error: El módulo VLANs debe estar activo."
        return True, "Dependencias satisfechas"

    # 2. WAN es la base de todo (para otros módulos)
    if get_module_status_by_name(base_dir, "wan") != 1:
        return False, "Error: El módulo WAN debe estar activo."

    # 3. VLANs, NAT y DHCP requieren WAN (ya chequeado)
    if module_name in ["vlans", "nat", "dhcp"]:
        return True, "Dependencias satisfechas"

    # 4. Firewall, Ebtables, DMZ requieren VLANs (A menos que Firewall se use para Wi-Fi)
    if get_module_status_by_name(base_dir, "vlans") != 1:
        if module_name == "firewall" and get_module_status_by_name(base_dir, "wifi") == 1:
            pass
        else:
            return False, "Error: El módulo VLANs debe estar activo."

    # 5. Firewall, Ebtables, DMZ requieren Tagging (A menos que Firewall se use para Wi-Fi)
    if get_module_status_by_name(base_dir, "tagging") != 1:
        if module_name == "firewall" and get_module_status_by_name(base_dir, "wifi") == 1:
            pass
        else:
            return False, "Error: El módulo Tagging debe estar activo."

    if module_name in ["firewall", "ebtables"]:
        return True, "Dependencias satisfechas"

    # 6. DMZ requiere Firewall
    if module_name == "dmz":
        if get_module_status_by_name(base_dir, "firewall") != 1:
            return False, "Error: El módulo Firewall debe estar activo para usar DMZ."

    return True, "Dependencias satisfechas"
