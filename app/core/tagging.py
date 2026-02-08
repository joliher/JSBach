# app/core/tagging.py

import os
import json
import subprocess
from typing import Dict, Any, Tuple, Optional
from ..utils.global_functions import create_module_config_directory, create_module_log_directory, check_module_dependencies, get_module_status
from ..utils.validators import sanitize_interface_name, validate_interface_name
from ..utils.helpers import (
    load_json_config, save_json_config, update_module_status, run_command
)
from .helpers import run_cmd, parse_vlan_range, format_vlan_list, tagging_bridge_exists

# Config file in V4 structure
CONFIG_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "config", "tagging", "tagging.json")
)

# Alias helpers para compatibilidad
_load_config = lambda: load_json_config(CONFIG_FILE, {"interfaces": [], "status": 0})
def _save_config(data):
    success = save_json_config(CONFIG_FILE, data)
    if not success:
        print(f"Advertencia: No se pudo guardar configuración de Tagging en {CONFIG_FILE}")
    return success

_update_status = lambda status: update_module_status(CONFIG_FILE, status)
_sanitize_interface_name = sanitize_interface_name  # Alias para compatibilidad

# Aliases para funciones de helpers
_run_cmd = run_cmd
_bridge_exists = tagging_bridge_exists
_parse_vlan_range = parse_vlan_range
_format_vlan_list = format_vlan_list


# --------------------------------
# Acciones públicas (Admin API)
# --------------------------------


def start(params: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
    create_module_config_directory("tagging")
    create_module_log_directory("tagging")

    # Verificar dependencias
    deps_ok, deps_msg = check_module_dependencies("tagging")
    if not deps_ok:
        return False, deps_msg
    
    cfg = _load_config()
    interfaces = cfg.get("interfaces", [])
    
    if not interfaces:
        return False, "No hay interfaces configuradas para tagging"
    
    if not _bridge_exists():
        return False, "Bridge br0 no existe. Configure VLANs primero"

    if get_module_status("tagging") == 1 and _tagging_already_started(interfaces):
        return False, "Tagging ya iniciado"

    if _tagging_already_started(interfaces):
        return False, "Tagging ya iniciado"
    
    # Solo tocar VLAN 1 si hay interfaces físicas
    if interfaces:
        _run_cmd(["/usr/sbin/bridge", "vlan", "del", "dev", "br0", "vid", "1", "pvid", "untagged"], ignore_error=True)
    
    # Acumular errores y resultados
    errors = []
    success_list = []
    
    # Configurar TAG/UNTAG en interfaces físicas
    for iface in interfaces:
        name = iface.get("name")
        vlan_untag = iface.get("vlan_untag")
        vlan_tag = iface.get("vlan_tag")
        
        if not name:
            continue
        
        # Validar nombre de interfaz seguro
        valid, error = validate_interface_name(name)
        if not valid:
            return False, f"Nombre de interfaz inválido: '{name}'. {error}"

        if name == "br0" or name.startswith("br0."):
            return False, "Nombre de interfaz inválido: 'br0' y sus subinterfaces no son permitidas en tagging"
        
        iface_errors = []
        
        # Validar que la interfaz física existe
        success, error = _run_cmd(["/usr/sbin/ip", "link", "show", name])
        if not success:
            iface_errors.append(f"interfaz no existe: {error}")
            errors.append(f"  {name}: " + ", ".join(iface_errors))
            continue
        
        # Agregar interfaz al bridge
        success, error = _run_cmd(["/usr/sbin/ip", "link", "set", name, "master", "br0"], ignore_error=True)
        if not success:
            iface_errors.append(f"agregando al bridge: {error}")
        
        success, error = _run_cmd(["/usr/sbin/ip", "link", "set", name, "up"])
        if not success:
            iface_errors.append(f"habilitando: {error}")
        
        # Eliminar VLAN 1 por defecto en la interfaz
        _run_cmd(["/usr/sbin/bridge", "vlan", "del", "dev", name, "vid", "1", "pvid", "untagged"], ignore_error=True)
        
        # VLAN UNTAG
        if vlan_untag:
            success, error = _run_cmd(["/usr/sbin/bridge", "vlan", "add", "dev", name, "vid", str(vlan_untag), "pvid", "untagged"], ignore_error=True)
            if not success:
                iface_errors.append(f"UNTAG VLAN {vlan_untag}: {error}")
            success, error = _run_cmd(["/usr/sbin/bridge", "vlan", "add", "dev", "br0", "vid", str(vlan_untag), "self"], ignore_error=True)
            if not success:
                iface_errors.append(f"VLAN {vlan_untag} al bridge: {error}")
        
        # VLAN TAG
        if vlan_tag:
            for vid in str(vlan_tag).split(","):
                vid = vid.strip()
                if vid:
                    success, error = _run_cmd(["/usr/sbin/bridge", "vlan", "add", "dev", name, "vid", vid], ignore_error=True)
                    if not success:
                        iface_errors.append(f"TAG VLAN {vid}: {error}")
                    success, error = _run_cmd(["/usr/sbin/bridge", "vlan", "add", "dev", "br0", "vid", vid, "self"], ignore_error=True)
                    if not success:
                        iface_errors.append(f"VLAN {vid} al bridge: {error}")
        
        if iface_errors:
            errors.append(f"  {name}: " + ", ".join(iface_errors))
        else:
            config_info = []
            if vlan_untag:
                config_info.append(f"UNTAG={vlan_untag}")
            if vlan_tag:
                config_info.append(f"TAG={vlan_tag}")
            success_list.append(f"  {name}: " + ", ".join(config_info) if config_info else f"  {name}")
    
    _update_status(1 if len(success_list) > 0 else 0)
    
    result_msg = ""
    
    if success_list:
        result_msg += "Interfaces configuradas correctamente:\n" + "\n".join(success_list)
    
    if errors:
        if result_msg:
            result_msg += "\n\n"
        result_msg += "Errores en interfaces:\n" + "\n".join(errors)
        return True if success_list else False, result_msg
    
    return True, result_msg if result_msg else "Tagging configurado correctamente"


def stop(params: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
    create_module_config_directory("tagging")
    create_module_log_directory("tagging")
    
    cfg = _load_config()
    interfaces = cfg.get("interfaces", [])
    
    # Remover interfaces del bridge y limpiar configuración VLAN
    for iface in interfaces:
        name = iface.get("name")
        if not name:
            continue
        
        # Remover del bridge
        _run_cmd(["/usr/sbin/ip", "link", "set", name, "nomaster"], ignore_error=True)
        
        # Limpiar configuración VLAN
        _run_cmd(["/usr/sbin/bridge", "vlan", "del", "dev", name, "vid", "1-4094"], ignore_error=True)
    
    _update_status(0)
    return True, "Tagging detenido"


def restart(params: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
    ok, msg = stop()
    if not ok:
        return False, msg
    return start()


def status(params: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
    create_module_config_directory("tagging")
    create_module_log_directory("tagging")
    
    cfg = _load_config()
    interfaces = cfg.get("interfaces", [])
    
    # Verificar si el bridge br0 existe
    br0_exists = _bridge_exists()
    br0_is_up = False
    
    if br0_exists:
        try:
            result = subprocess.run(
                ["sudo", "/usr/sbin/ip", "a", "show", "br0"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )
            br0_is_up = "state UP" in result.stdout
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass
    
    status_lines = ["Estado de Tagging:", "=" * 50]
    
    if not br0_exists:
        status_lines.append("🔴 Bridge br0: NO EXISTE")
        status_lines.append("\n⚠️ El tagging requiere que el bridge br0 esté creado")
        return True, "\n".join(status_lines)
    
    br0_status = "🟢 UP" if br0_is_up else "🔴 DOWN"
    status_lines.append(f"Bridge br0: {br0_status}")
    
    # Verificar cada interfaz configurada
    status_lines.append(f"\nInterfaces configuradas: {len(interfaces)}")
    status_lines.append("-" * 50)
    
    if interfaces:
        for iface in interfaces:
            name = iface.get('name')
            vlan_untag = iface.get('vlan_untag', '')
            vlan_tag = iface.get('vlan_tag', '')
            
            # Verificar si la interfaz existe y está UP
            try:
                result = subprocess.run(
                    ["sudo", "/usr/sbin/ip", "a", "show", name],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=5
                )
                is_up = "state UP" in result.stdout
                is_master_br0 = "master br0" in result.stdout
                iface_status = "🟢 UP" if is_up else "🔴 DOWN"
                bridge_status = " ✅ Conectada a br0" if is_master_br0 else " ⚠️ No conectada a br0"
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                iface_status = "❌ NO EXISTE"
                bridge_status = ""
            
            status_lines.append(f"\nInterfaz: {name} [{iface_status}]{bridge_status}")
            status_lines.append(f"  VLAN sin etiquetar (UNTAG): {vlan_untag if vlan_untag else 'N/A'}")
            status_lines.append(f"  VLANs etiquetadas (TAG): {vlan_tag if vlan_tag else 'N/A'}")
    else:
        status_lines.append("\n(Sin interfaces configuradas)")
    
    # Mostrar estado del bridge VLAN
    status_lines.append("\n" + "=" * 50)
    status_lines.append("Estado de VLAN en bridge:")
    status_lines.append("-" * 50)
    
    try:
        result = subprocess.run(
            ["sudo", "bridge", "vlan", "show"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        if result.stdout.strip():
            status_lines.append(result.stdout.rstrip())
        else:
            status_lines.append("(sin datos)")
    except subprocess.CalledProcessError:
        status_lines.append("Error obteniendo estado del bridge")
    except subprocess.TimeoutExpired:
        status_lines.append("Timeout obteniendo estado del bridge")
    
    return True, "\n".join(status_lines)


def config(params: Dict[str, Any]) -> Tuple[bool, str]:
    create_module_config_directory("tagging")
    create_module_log_directory("tagging")
    
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
        name = params.get("name")
        if not name:
            return False, "Falta parámetro obligatorio 'name'"
        
        if not isinstance(name, str):
            return False, f"Error: 'name' debe ser una cadena, recibido: {type(name).__name__}"
        
        name = name.strip()
        
        if not name:
            return False, "Error: 'name' no puede estar vacío"
        
        # Validar formato de nombre de interfaz
        valid, error = validate_interface_name(name)
        if not valid:
            return False, f"Error: nombre de interfaz inválido: '{name}'. {error}"

        if name == "br0" or name.startswith("br0."):
            return False, "Error: nombre de interfaz inválido. 'br0' y sus subinterfaces no son permitidas en tagging"
        
        # Normalizar campos vacíos
        vlan_untag = params.get("vlan_untag", "")
        vlan_tag = params.get("vlan_tag", "")
        
        # Validación INICIAL: Al menos uno de UNTAG o TAG debe ser proporcionado
        if not vlan_untag and not vlan_tag:
            return False, (
                f"❌ Error de configuración en interfaz {name}: "
                f"Debe proporcionar UNTAG o TAG (o ambos para validar conflicto).\n"
                f"  • UNTAG: Acceso a una sola VLAN (vlan_untag: '1')\n"
                f"  • TAG: Troncal con múltiples VLANs (vlan_tag: '10,20,30')"
            )
        
        # Validar vlan_untag si se proporciona
        if vlan_untag:
            if not isinstance(vlan_untag, (str, int)):
                return False, f"Error: 'vlan_untag' debe ser una cadena o número, recibido: {type(vlan_untag).__name__}"
            
            try:
                untag_id = int(vlan_untag)
                if untag_id < 1 or untag_id > 4094:
                    return False, f"Error: 'vlan_untag' debe estar entre 1 y 4094, recibido: {untag_id}"
                vlan_untag = str(untag_id)
            except (ValueError, TypeError):
                return False, f"Error: 'vlan_untag' debe ser un número válido, recibido: {vlan_untag}"
        
        # Validar vlan_tag si se proporciona
        if vlan_tag:
            if not isinstance(vlan_tag, str):
                return False, f"Error: 'vlan_tag' debe ser una cadena, recibido: {type(vlan_tag).__name__}"
            
            # Puede ser lista separada por comas o sintaxis con rangos (1,2,3-10,12)
            vlan_tag = vlan_tag.strip()
            if vlan_tag:
                # Parsear la sintaxis de rangos
                parsed_vlans = _parse_vlan_range(vlan_tag)
                if not parsed_vlans:
                    return False, f"Error: 'vlan_tag' no contiene VLANs válidas. Formato válido: '1,2,3-10,12'"
                
                # Convertir a formato comprimido para guardar
                vlan_tag = ",".join(parsed_vlans)
        
        # Cargar VLANs configuradas para validar existencia
        vlans_cfg_path = os.path.join(os.path.dirname(CONFIG_FILE), "..", "vlans", "vlans.json")
        configured_vlan_ids = []
        if os.path.exists(vlans_cfg_path):
            try:
                with open(vlans_cfg_path, 'r') as f:
                    vlans_cfg = json.load(f)
                    configured_vlan_ids = [v.get("id") for v in vlans_cfg.get("vlans", [])]
            except Exception:
                pass  # Si falla la lectura, permitir configuración (puede que VLANs no estén configuradas aún)
        
        # Validar que VLANs existan si hay VLANs configuradas
        if configured_vlan_ids:
            if vlan_untag and int(vlan_untag) not in configured_vlan_ids:
                return False, f"Error: VLAN {vlan_untag} no existe en el sistema. Configure la VLAN primero con el módulo VLANs."
            
            if vlan_tag:
                tag_list = _parse_vlan_range(vlan_tag)
                for tag_id_str in tag_list:
                    tag_id = int(tag_id_str)
                    if tag_id not in configured_vlan_ids:
                        return False, f"Error: VLAN {tag_id} no existe en el sistema. Configure la VLAN primero con el módulo VLANs."
        
        # ===== VALIDACIÓN DE CONFLICTO UNTAG/TAG =====
        # Una interfaz NO puede ser UNTAGGED en una VLAN Y TAGGED en otras
        if vlan_untag and vlan_tag:
            return False, (
                f"❌ Conflicto de configuración VLAN en interfaz {name}: "
                f"No puede estar UNTAGGED en VLAN {vlan_untag} Y TAGGED en VLANs {vlan_tag}. "
                f"Una interfaz debe estar en UNO u OTRO modo:\n"
                f"  • UNTAG: Acceso a solo una VLAN (vlan_untag: '{vlan_untag}')\n"
                f"  • TAG: Troncal con múltiples VLANs (vlan_tag: '{vlan_tag}')"
            )
        
        # VALIDACIÓN: Si interfaz ya existe en ebtables con config incompatible, rechazar reconfiguración
        ebtables_cfg_path = os.path.join(os.path.dirname(CONFIG_FILE), "..", "ebtables", "ebtables.json")
        existing_iface = next((i for i in cfg["interfaces"] if i.get("name") == name), None)
        
        if existing_iface and os.path.exists(ebtables_cfg_path):
            try:
                with open(ebtables_cfg_path, 'r') as f:
                    ebtables_cfg = json.load(f)
                    # Buscar si esta interfaz está siendo usada
                    for vlan_id, vlan_data in ebtables_cfg.items():
                        if vlan_id == "status":
                            continue
                        interfaces = vlan_data.get("interfaces", [])
                        if name in interfaces:
                            # Interfaz está siendo usada en aislar
                            # Si la configuración actual y la nueva son incompatibles, rechazar
                            old_vlan_untag = existing_iface.get("vlan_untag", "")
                            if old_vlan_untag != vlan_untag or vlan_tag:
                                return False, (
                                    f"❌ Error: Interfaz {name} está siendo usada por ebtables VLAN {vlan_id}. "
                                    f"Primero desaísla VLAN {vlan_id} antes de cambiar la configuración."
                                )
            except Exception:
                return False, "Error: no se pudo leer la configuración de ebtables para validar dependencias"
        
        # Eliminar si ya existía la interfaz
        cfg["interfaces"] = [i for i in cfg["interfaces"] if i.get("name") != name]
        
        # Agregar nueva
        cfg["interfaces"].append({
            "name": name,
            "vlan_untag": str(vlan_untag) if vlan_untag else "",
            "vlan_tag": str(vlan_tag) if vlan_tag else ""
        })
        if not _save_config(cfg):
            return False, f"Error guardando configuración de tagging en {CONFIG_FILE}"
        return True, f"Interfaz {name} agregada"
    
    elif action == "remove":
        name = params.get("name")
        if not name:
            return False, "Falta parámetro obligatorio 'name'"
        
        if not isinstance(name, str):
            return False, f"Error: 'name' debe ser una cadena, recibido: {type(name).__name__}"
        
        name = name.strip()
        
        if not name:
            return False, "Error: 'name' no puede estar vacío"
        
        # VALIDACIÓN: Verificar que la interfaz no esté siendo usada por ebtables
        ebtables_cfg_path = os.path.join(os.path.dirname(CONFIG_FILE), "..", "ebtables", "ebtables.json")
        if os.path.exists(ebtables_cfg_path):
            try:
                with open(ebtables_cfg_path, 'r') as f:
                    ebtables_cfg = json.load(f)
                    # Buscar si esta interfaz está en alguna VLAN aislada
                    for vlan_id, vlan_data in ebtables_cfg.items():
                        if vlan_id == "status":
                            continue
                        interfaces = vlan_data.get("interfaces", [])
                        if name in interfaces:
                            return False, (
                                f"❌ Error: Interfaz {name} está siendo usada por ebtables en VLAN {vlan_id}. "
                                f"Primero desaísla VLAN {vlan_id} usando: ebtables desaislar {{'vlan_id': {vlan_id}}}"
                            )
            except Exception:
                return False, "Error: no se pudo leer la configuración de ebtables para validar dependencias"
        
        original_count = len(cfg["interfaces"])
        cfg["interfaces"] = [i for i in cfg["interfaces"] if i.get("name") != name]
        if len(cfg["interfaces"]) == original_count:
            return False, f"Interfaz {name} no encontrada"
        
        if not _save_config(cfg):
            return False, f"Error guardando configuración de tagging en {CONFIG_FILE}"
        return True, f"Interfaz {name} eliminada"
    
    elif action == "show":
        interfaces = cfg.get("interfaces", [])
        
        if params.get("format") == "json":
            return True, json.dumps(interfaces)

        if not interfaces:
            return True, "No hay interfaces configuradas"
        
        result = "Interfaces configuradas:\n"
        for iface in interfaces:
            result += f"  Name: {iface.get('name')}, UNTAG: {iface.get('vlan_untag', '')}, TAG: {iface.get('vlan_tag', '')}\n"
        return True, result.rstrip()
    
    else:
        return False, f"Acción no válida: '{action}'. Use: add, remove, show"


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


def _parse_bridge_vlan_output(output: str) -> Dict[str, Dict[str, set]]:
    vlan_map: Dict[str, Dict[str, set]] = {}
    last_iface = None

    for line in output.splitlines():
        if not line.strip() or line.startswith("port"):
            continue
        parts = line.split()

        iface = None
        vlan_id = None
        flags = set()

        if parts[0].isdigit() and last_iface:
            iface = last_iface
            vlan_id = parts[0]
            flags = set(parts[1:]) if len(parts) > 1 else set()
        elif len(parts) >= 2:
            iface = parts[0]
            vlan_id = parts[1]
            flags = set(parts[2:]) if len(parts) > 2 else set()
            last_iface = iface
        else:
            continue

        if iface not in vlan_map:
            vlan_map[iface] = {"vlans": set(), "pvids": set()}

        vlan_map[iface]["vlans"].add(vlan_id)
        if "PVID" in flags:
            vlan_map[iface]["pvids"].add(vlan_id)

    return vlan_map


def _interface_in_bridge(interface: str) -> bool:
    try:
        result = subprocess.run(
            ["/usr/sbin/ip", "a", "show", interface],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        return "master br0" in result.stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def _tagging_already_started(interfaces: list) -> bool:
    if not interfaces:
        return False

    success, output = _run_cmd(["/usr/sbin/bridge", "vlan", "show"])
    if not success:
        return False

    vlan_map = _parse_bridge_vlan_output(output)

    for iface in interfaces:
        name = iface.get("name")
        if not name or not os.path.exists(f"/sys/class/net/{name}"):
            return False
        if not _interface_in_bridge(name):
            return False

        iface_vlans = vlan_map.get(name, {"vlans": set(), "pvids": set()})
        vlan_untag = str(iface.get("vlan_untag") or "").strip()
        vlan_tag = str(iface.get("vlan_tag") or "").strip()

        if vlan_untag:
            if vlan_untag not in iface_vlans["vlans"]:
                return False
            if vlan_untag not in iface_vlans["pvids"]:
                return False

        if vlan_tag:
            tag_list = _parse_vlan_range(vlan_tag)
            for tag_id in tag_list:
                if tag_id not in iface_vlans["vlans"]:
                    return False

    return True