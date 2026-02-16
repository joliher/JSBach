# app/core/ebtables.py
# Módulo de Ebtables - Aislamiento de VLANs a nivel L2
# Arquitectura jerárquica con cadenas por VLAN

import subprocess
import json
import os
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
import logging
import fcntl
import re
from typing import Dict, Any, Tuple, List
from ...utils.global_helpers import module_helpers as mh, io_helpers as ioh
from ...utils.validators import sanitize_interface_name
from .helpers import (
    ensure_dirs, load_ebtables_config, save_ebtables_config,
    load_vlans_config, load_wan_config, load_tagging_config,
    build_vlan_interface_map, check_wan_active, check_vlans_active,
    check_tagging_active, check_interface_vlan_conflict, check_vlan_already_isolated, check_dependencies,
    update_status, run_ebtables,
    create_vlan_chain, delete_vlan_chain, add_vlan_interface_to_forward, remove_vlan_interface_from_forward,
    apply_isolation, remove_isolation,
    validate_mac_address, normalize_mac_address, apply_mac_whitelist_rules, remove_mac_whitelist_rules,
    validate_wan_interface
)

# Configurar logging
logger = logging.getLogger(__name__)

# Rutas de configuración
# BASE_DIR ya está definido correctamente arriba (line 8)
EBTABLES_CONFIG_FILE = os.path.join(BASE_DIR, "config", "ebtables", "ebtables.json")
VLANS_CONFIG_FILE = os.path.join(BASE_DIR, "config", "vlans", "vlans.json")
WAN_CONFIG_FILE = os.path.join(BASE_DIR, "config", "wan", "wan.json")
TAGGING_CONFIG_FILE = os.path.join(BASE_DIR, "config", "tagging", "tagging.json")


# =============================================================================
# ALIASES DE COMPATIBILIDAD
# =============================================================================

_ensure_dirs = ensure_dirs
_load_ebtables_config = load_ebtables_config
_save_ebtables_config = save_ebtables_config
_load_vlans_config = load_vlans_config
_load_wan_config = load_wan_config
_load_tagging_config = load_tagging_config
_build_vlan_interface_map = build_vlan_interface_map
_check_wan_active = check_wan_active
_check_vlans_active = check_vlans_active
_check_tagging_active = check_tagging_active
_check_interface_vlan_conflict = check_interface_vlan_conflict
_check_vlan_already_isolated = check_vlan_already_isolated
_check_dependencies = check_dependencies
_update_status = update_status
_run_ebtables = run_ebtables
_create_vlan_chain = create_vlan_chain
_delete_vlan_chain = delete_vlan_chain
_add_vlan_interface_to_forward = add_vlan_interface_to_forward
_remove_vlan_interface_from_forward = remove_vlan_interface_from_forward
_apply_isolation = apply_isolation
_remove_isolation = remove_isolation
_validate_mac_address = validate_mac_address
_normalize_mac_address = normalize_mac_address
_apply_mac_whitelist_rules = apply_mac_whitelist_rules
_remove_mac_whitelist_rules = remove_mac_whitelist_rules
_sanitize_interface_name = sanitize_interface_name
_validate_wan_interface = validate_wan_interface


# =============================================================================
# ACCIONES PÚBLICAS
# =============================================================================

def start(params: Dict[str, Any] = None) -> Tuple[bool, str]:
    """Iniciar el sistema de bridge/ebtables con estructura jerárquica.
    
    Estructura:
    FORWARD → FORWARD_VLAN_1 (reglas VLAN 1)
           → FORWARD_VLAN_10 (reglas VLAN 10)
           → DROP (regla final)
    
    Dependencias: WAN, VLANs, Tagging deben estar activos
    """
    _ensure_dirs()
    logger.info("=== INICIO: ebtables start ===")
    
    # Verificar dependencias (WAN, VLANs, Tagging)
    deps_ok, deps_msg = mh.check_module_dependencies(BASE_DIR, "ebtables")
    if not deps_ok:
        logger.error(f"Dependencias no satisfechas: {deps_msg}")
        return False, deps_msg
    
    # Obtener interfaz WAN (ya sabemos que está activa)
    wan_active, wan_iface = _check_wan_active()
    if not wan_active or not wan_iface:
        logger.error("WAN no activa o sin interfaz")
        return False, "Error: WAN no activa o sin interfaz"

    if not _sanitize_interface_name(wan_iface):
        logger.error(f"Interfaz WAN inválida: {wan_iface}")
        return False, f"Error: Interfaz WAN inválida: {wan_iface}"

    wan_valid, wan_msg = _validate_wan_interface(wan_iface)
    if not wan_valid:
        logger.error(wan_msg)
        return False, f"Error: {wan_msg}"
    
    # Cargar configuración de VLANs
    vlans_cfg = _load_vlans_config()
    vlans = vlans_cfg.get("vlans", [])
    
    # Cargar/inicializar configuración de ebtables
    ebtables_cfg = _load_ebtables_config()
    if "vlans" not in ebtables_cfg:
        ebtables_cfg["vlans"] = {}
    
    # Cargar configuración de tagging
    tagging_cfg = _load_tagging_config()
    
    # Construir mapa VLAN → interfaces físicas
    vlan_iface_map = _build_vlan_interface_map(vlans, tagging_cfg)
    logger.info(f"Mapa VLAN→Interfaces: {vlan_iface_map}")
    
    # Sincronizar: eliminar VLANs obsoletas de ebtables.json
    active_vlan_ids = {str(vlan.get("id")) for vlan in vlans if vlan.get("id") is not None}
    vlans_to_remove = [vid for vid in ebtables_cfg["vlans"].keys() if vid not in active_vlan_ids]
    
    for vlan_id in vlans_to_remove:
        logger.info(f"Eliminando VLAN {vlan_id} obsoleta de ebtables.json")
        _delete_vlan_chain(int(vlan_id))
        del ebtables_cfg["vlans"][vlan_id]
    
    results = []
    errors = []
    
    # Procesar cada VLAN
    for vlan in vlans:
        vlan_id = vlan.get("id")
        vlan_name = vlan.get("name", f"VLAN{vlan_id}")
        vlan_id_str = str(vlan_id)
        
        logger.info(f"Procesando VLAN {vlan_id} ({vlan_name})")
        
        # Validar que la VLAN tenga ID válido
        if not vlan_id or not isinstance(vlan_id, int):
            errors.append(f"VLAN con ID inválido: {vlan_id}")
            continue
        
        # Inicializar configuración de VLAN si no existe
        if vlan_id_str not in ebtables_cfg["vlans"]:
            ebtables_cfg["vlans"][vlan_id_str] = {
                "name": vlan_name,
                "isolated": False  # Por defecto NO aislada
            }
            # Si es VLAN 1, inicializar whitelist habilitada por defecto
            if vlan_id == 1:
                ebtables_cfg["vlans"][vlan_id_str]["mac_whitelist_enabled"] = True
                ebtables_cfg["vlans"][vlan_id_str]["mac_whitelist"] = []
                logger.info("VLAN 1 inicializada con MAC whitelist habilitada por defecto")
        else:
            # Actualizar nombre de la VLAN
            ebtables_cfg["vlans"][vlan_id_str]["name"] = vlan_name
            if vlan_id == 1:
                # Rehabilitar whitelist en cada inicio del módulo
                if ebtables_cfg["vlans"][vlan_id_str].get("mac_whitelist_enabled") is False:
                    logger.info("VLAN 1: Whitelist re-habilitada al iniciar el módulo")
                ebtables_cfg["vlans"][vlan_id_str]["mac_whitelist_enabled"] = True
        
        # Crear cadena para la VLAN
        if not _create_vlan_chain(vlan_id):
            errors.append(f"VLAN {vlan_id}: Error creando cadena ebtables")
            logger.error(f"Error creando cadena para VLAN {vlan_id}")
            continue
        
        # Las reglas en FORWARD se agregarán solo si la VLAN está aislada (en _apply_isolation)
        # Si no está aislada, la cadena existe pero vacía (sin reglas en FORWARD)

        
        # Aplicar aislamiento si está configurado
        is_isolated = ebtables_cfg["vlans"][vlan_id_str].get("isolated", False)
        
        # Obtener interfaces de esta VLAN desde el mapa
        vlan_interfaces = vlan_iface_map.get(vlan_id, [])
        
        if is_isolated:
            if not vlan_interfaces:
                errors.append(f"VLAN {vlan_id}: No hay interfaces configuradas en Tagging")
                logger.warning(f"VLAN {vlan_id} aislada sin interfaces configuradas")
                continue
            if not _apply_isolation(vlan_id, wan_iface, vlan_interfaces):
                errors.append(f"VLAN {vlan_id}: Error aplicando aislamiento")
                logger.error(f"Error aplicando aislamiento a VLAN {vlan_id}")
                continue
            logger.info(f"VLAN {vlan_id} configurada como AISLADA con interfaces: {vlan_interfaces}")
            results.append(f"VLAN {vlan_id} ({vlan_name}): AISLADA (interfaces: {','.join(vlan_interfaces)})")
        else:
            # Asegurar que no tenga reglas de aislamiento
            _remove_isolation(vlan_id)
            logger.info(f"VLAN {vlan_id} configurada como NO AISLADA")
            results.append(f"VLAN {vlan_id} ({vlan_name}): NO AISLADA")
        
        # Aplicar MAC whitelist para VLAN 1 si está habilitada
        if vlan_id == 1:
            mac_whitelist_enabled = ebtables_cfg["vlans"][vlan_id_str].get("mac_whitelist_enabled", False)
            mac_whitelist = ebtables_cfg["vlans"][vlan_id_str].get("mac_whitelist", [])
            
            if mac_whitelist_enabled:
                if _apply_mac_whitelist_rules(vlan_id, wan_iface, mac_whitelist):
                    logger.info(f"VLAN 1: MAC whitelist aplicada con {len(mac_whitelist)} entradas")
                    if mac_whitelist:
                        results.append(f"VLAN 1: Whitelist activa ({len(mac_whitelist)} MACs)")
                    else:
                        results.append(f"VLAN 1: Whitelist habilitada (sin MACs configuradas)")
                else:
                    errors.append(f"VLAN 1: Error aplicando MAC whitelist")
                    logger.error(f"Error aplicando MAC whitelist a VLAN 1")
            else:
                logger.info(f"VLAN 1: MAC whitelist deshabilitada")
    
    # Guardar configuración actualizada
    ebtables_cfg["status"] = 1
    ebtables_cfg["wan_interface"] = wan_iface
    saved = _save_ebtables_config(ebtables_cfg)
    if not saved:
        errors.append("Error guardando configuración de ebtables en disco")
        logger.warning("No se pudo persistir ebtables.json")
    
    # Construir mensaje de resultado
    status_title = "✅ Ebtables iniciado correctamente" if not errors else "⚠️ Ebtables iniciado con advertencias"
    message_parts = [status_title]
    message_parts.append(f"WAN: {wan_iface}")
    message_parts.append(f"VLANs procesadas: {len(results)}")
    
    if results:
        message_parts.append("\nVLANs configuradas:")
        message_parts.extend(results)
    
    if errors:
        message_parts.append("\n⚠️ Advertencias:")
        message_parts.extend(errors)
        logger.warning(f"Ebtables iniciado con advertencias: {errors}")
    
    final_message = "\n".join(message_parts)
    logger.info(final_message)
    logger.info("=== FIN: ebtables start ===")
    
    success = len(errors) == 0
    return success, final_message


def stop(params: Dict[str, Any] = None) -> Tuple[bool, str]:
    """Detener el sistema de bridge/ebtables."""
    _ensure_dirs()
    logger.info("=== INICIO: bridge stop ===")
    
    ebtables_cfg = _load_ebtables_config()
    vlans = ebtables_cfg.get("vlans", {})
    
    # Eliminar todas las cadenas de VLANs
    for vlan_id_str in vlans.keys():
        vlan_id = int(vlan_id_str)
        _delete_vlan_chain(vlan_id)
    
    # Actualizar estado
    _update_status(0)
    
    logger.info("Bridge detenido correctamente")
    logger.info("=== FIN: bridge stop ===")
    return True, "Bridge detenido correctamente"


def restart(params: Dict[str, Any] = None) -> Tuple[bool, str]:
    """Reiniciar el sistema de bridge/ebtables."""
    _ensure_dirs()
    logger.info("=== INICIO: bridge restart ===")
    
    # Detener
    ok, msg = stop()
    if not ok:
        return False, f"Error al detener: {msg}"
    
    # Iniciar
    ok, msg = start()
    if not ok:
        return False, f"Error al iniciar: {msg}"
    
    logger.info("=== FIN: bridge restart ===")
    return True, "Bridge reiniciado correctamente"


def status(params: Dict[str, Any] = None) -> Tuple[bool, str]:
    """Obtener estado del bridge/ebtables y sus dependencias."""
    _ensure_dirs()
    
    ebtables_cfg = _load_ebtables_config()
    module_status = ebtables_cfg.get("status", 0)
    vlans = ebtables_cfg.get("vlans", {})
    
    lines = []
    
    # ========== ESTADO DEL MÓDULO ==========
    if module_status == 0:
        lines.append("🌉 EBTABLES - MÓDULO INACTIVO")
        lines.append("=" * 50)
        lines.append("")
        lines.append("❌ El módulo EBTABLES está PARADO")
        lines.append("")
        lines.append("Para activar el módulo:")
        lines.append("1. Asegúrate de que WAN, VLANs y Tagging estén activos")
        lines.append("2. Haz clic en 'EBTABLES START' en la interfaz web")
        lines.append("")
        lines.append(f"VLANs con configuración guardada: {len(vlans)}")
        return True, "\n".join(lines)
    
    # Módulo activo - mostrar estado completo
    lines.append("🌉 EBTABLES - MÓDULO ACTIVO")
    lines.append("=" * 50)
    lines.append("")
    
    # ========== DEPENDENCIAS ==========
    lines.append("📦 DEPENDENCIAS:")
    lines.append("-" * 50)
    
    # Verificar WAN
    wan_active, wan_iface = _check_wan_active()
    if wan_active:
        lines.append(f"✅ WAN: Activo (interfaz: {wan_iface})")
    else:
        lines.append("❌ WAN: INACTIVO (requerido para bridge)")
    
    # Verificar VLANs
    vlans_ok, vlans_msg = _check_vlans_active()
    if vlans_ok:
        vlans_cfg = _load_vlans_config()
        vlans_list = vlans_cfg.get("vlans", [])
        lines.append(f"✅ VLANs: Activo ({len(vlans_list)} VLANs configuradas)")
    else:
        lines.append(f"❌ VLANs: {vlans_msg}")
    
    # Verificar Tagging
    tagging_ok, tagging_msg = _check_tagging_active()
    if tagging_ok:
        tagging_cfg = _load_tagging_config()
        ifaces = tagging_cfg.get("interfaces", [])
        lines.append(f"✅ Tagging: Activo ({len(ifaces)} interfaces configuradas)")
    else:
        lines.append(f"❌ Tagging: {tagging_msg}")
    
    # Verificar si todas las dependencias están ok
    all_deps_ok = wan_active and vlans_ok and tagging_ok
    lines.append("")
    
    # ========== ESTADO GENERAL ==========
    lines.append("🌉 ESTADO OPERACIONAL:")
    lines.append("-" * 50)
    
    if not all_deps_ok:
        lines.append("⚠️ No todas las dependencias están activas.")
        lines.append("   El módulo EBTABLES no puede operar correctamente.")
        lines.append("")
        lines.append(f"VLANs aisladas en configuración: {len(vlans)}")
        return True, "\n".join(lines)
    
    if not vlans:
        lines.append("ℹ️  Sin VLANs configuradas en ebtables")
        return True, "\n".join(lines)
    
    lines.append(f"✅ Todas las dependencias activas")
    lines.append(f"VLANs configuradas: {len(vlans)}")
    lines.append("-" * 50)
    lines.append("")
    
    # ========== DETALLE DE VLANs ==========
    for vlan_id_str, vlan_data in sorted(vlans.items(), key=lambda x: int(x[0])):
        vlan_name = vlan_data.get("name", "")
        isolated = vlan_data.get("isolated", False)
        
        status_str = "🔒 AISLADA" if isolated else "🔓 NO AISLADA"
        lines.append(f"VLAN {vlan_id_str} ({vlan_name}): {status_str}")
        
        # Mostrar reglas activas
        chain_name = f"FORWARD_VLAN_{vlan_id_str}"
        success, output = _run_ebtables(["-L", chain_name])
        if success and output.strip():
            # Contar reglas (excluir líneas de cabecera)
            rules = [l for l in output.strip().split('\n') if l and not l.startswith('Bridge')]
            if len(rules) > 2:  # Más que solo cabeceras
                lines.append(f"  Reglas activas: {len(rules) - 2}")
        lines.append("")
    
    return True, "\n".join(lines)


def isolate(params: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Aislar una VLAN (solo permite tráfico con WAN).
    
    Requiere: WAN, VLANs y Tagging activos.
    """
    _ensure_dirs()
    
    if not params or "vlan_id" not in params:
        return False, "Error: Falta parámetro 'vlan_id'"
    
    try:
        vlan_id = int(params["vlan_id"])
    except (ValueError, TypeError):
        return False, f"Error: 'vlan_id' debe ser un número entero"
    
    # Verificar dependencias (WAN, VLANs, Tagging)
    deps_ok, deps_msg = _check_dependencies()
    if not deps_ok:
        logger.error(f"Dependencias no satisfechas al aislar VLAN {vlan_id}: {deps_msg}")
        return False, f"Error: {deps_msg}. Configure e inicie los módulos requeridos primero."
    
    # Obtener interfaz WAN (ya sabemos que está activa)
    wan_active, wan_iface = _check_wan_active()
    if not wan_active or not wan_iface:
        return False, "Error: WAN no activa o sin interfaz"

    wan_valid, wan_msg = _validate_wan_interface(wan_iface)
    if not wan_valid:
        return False, f"Error: {wan_msg}"
    
    # Verificar que la VLAN existe en vlans.json (sincronización)
    vlans_cfg = _load_vlans_config()
    vlans = vlans_cfg.get("vlans", [])
    vlan_exists = any(v.get("id") == vlan_id for v in vlans)
    if not vlan_exists:
        return False, f"Error: VLAN {vlan_id} no existe. Configure la VLAN primero."
    
    # Cargar configuración
    ebtables_cfg = _load_ebtables_config()
    vlan_id_str = str(vlan_id)
    
    if vlan_id_str not in ebtables_cfg.get("vlans", {}):
        return False, f"Error: VLAN {vlan_id} no está configurada en ebtables. Inicie ebtables primero."
    
    # Cargar tagging y construir mapa de interfaces
    tagging_cfg = _load_tagging_config()
    vlan_iface_map = _build_vlan_interface_map(vlans, tagging_cfg)
    vlan_interfaces = vlan_iface_map.get(vlan_id, [])
    
    # VALIDACIÓN 1: Verificar que la VLAN no esté ya aislada
    already_isolated_ok, already_isolated_msg = _check_vlan_already_isolated(vlan_id, ebtables_cfg)
    if not already_isolated_ok:
        logger.error(f"Intento de re-aislar VLAN {vlan_id}: {already_isolated_msg}")
        return False, already_isolated_msg

    if not vlan_interfaces:
        logger.warning(f"VLAN {vlan_id} sin interfases configuradas")
        return False, f"Error: VLAN {vlan_id} no tiene interfases configuradas. Configure interfases en tagging primero."
    
    logger.info(f"Aislando VLAN {vlan_id} con interfaces: {vlan_interfaces}")
    
    # Aplicar aislamiento
    if not _apply_isolation(vlan_id, wan_iface, vlan_interfaces):
        return False, f"Error aplicando aislamiento a VLAN {vlan_id}"
    
    # Actualizar configuración
    ebtables_cfg["vlans"][vlan_id_str]["isolated"] = True
    _save_ebtables_config(ebtables_cfg)
    
    logger.info(f"VLAN {vlan_id} aislada correctamente")
    return True, f"VLAN {vlan_id} aislada correctamente (solo tráfico con WAN permitido)\nInterfases: {','.join(vlan_interfaces) if vlan_interfaces else 'ninguna'}"


def unisolate(params: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Desaislar una VLAN (permitir todo el tráfico).
    
    Requiere: WAN, VLANs y Tagging activos.
    """
    _ensure_dirs()
    
    if not params or "vlan_id" not in params:
        return False, "Error: Falta parámetro 'vlan_id'"
    
    try:
        vlan_id = int(params["vlan_id"])
    except (ValueError, TypeError):
        return False, f"Error: 'vlan_id' debe ser un número entero"
    
    # Verificar dependencias (WAN, VLANs, Tagging)
    deps_ok, deps_msg = _check_dependencies()
    if not deps_ok:
        logger.error(f"Dependencias no satisfechas al desaislar VLAN {vlan_id}: {deps_msg}")
        return False, f"Error: {deps_msg}. Configure e inicie los módulos requeridos primero."
    
    # Cargar configuración
    ebtables_cfg = _load_ebtables_config()
    vlan_id_str = str(vlan_id)
    
    if vlan_id_str not in ebtables_cfg.get("vlans", {}):
        return False, f"Error: VLAN {vlan_id} no está configurada en bridge"
    
    # Obtener interfaces de la VLAN para remover las reglas en FORWARD
    vlans_cfg = _load_vlans_config()
    vlans = vlans_cfg.get("vlans", [])
    tagging_cfg = _load_tagging_config()
    vlan_iface_map = _build_vlan_interface_map(vlans, tagging_cfg)
    vlan_interfaces = vlan_iface_map.get(vlan_id, [])
    
    logger.info(f"Desaislando VLAN {vlan_id} con interfaces: {vlan_interfaces}")
    
    # Remover aislamiento (elimina reglas en FORWARD y cadena FORWARD_VLAN_X)
    if not _remove_isolation(vlan_id, vlan_interfaces):
        return False, f"Error removiendo aislamiento de VLAN {vlan_id}"
    
    # Actualizar configuración
    ebtables_cfg["vlans"][vlan_id_str]["isolated"] = False
    _save_ebtables_config(ebtables_cfg)
    
    logger.info(f"VLAN {vlan_id} desaislada correctamente")
    return True, f"VLAN {vlan_id} desaislada correctamente (todo el tráfico permitido)"


def add_mac(params: Dict[str, Any]) -> Tuple[bool, str]:
    """Agregar una dirección MAC a la whitelist de VLAN 1.
    
    Args:
        params: Diccionario con 'mac' (formato XX:XX:XX:XX:XX:XX)
    
    Returns:
        (True, mensaje) si éxito, (False, error) si falla
    """
    _ensure_dirs()
    
    if not params or "mac" not in params:
        return False, "Error: Falta parámetro 'mac'"
    
    mac = params.get("mac", "").strip()
    
    if not mac:
        logger.error("Error: MAC no proporcionada")
        return False, "Error: MAC requerida (formato: XX:XX:XX:XX:XX:XX)"
    
    # Validar formato de MAC
    if not _validate_mac_address(mac):
        logger.error(f"MAC inválida: {mac}")
        return False, f"Error: Formato de MAC inválido: {mac}\nUse formato: XX:XX:XX:XX:XX:XX"
    
    # Normalizar MAC
    mac_normalized = _normalize_mac_address(mac)
    
    # Cargar configuración
    ebtables_cfg = _load_ebtables_config()
    module_active = ebtables_cfg.get("status", 0) == 1
    
    # Asegurar que VLAN 1 existe
    if "vlans" not in ebtables_cfg:
        ebtables_cfg["vlans"] = {}
    if "1" not in ebtables_cfg["vlans"]:
        ebtables_cfg["vlans"]["1"] = {
            "name": "Admin",
            "isolated": False,
            "mac_whitelist_enabled": True,
            "mac_whitelist": []
        }
    
    vlan_1_cfg = ebtables_cfg["vlans"]["1"]
    if "mac_whitelist" not in vlan_1_cfg:
        vlan_1_cfg["mac_whitelist"] = []
    
    whitelist = vlan_1_cfg["mac_whitelist"]
    
    # Verificar que no sea un duplicado
    if mac_normalized in whitelist:
        logger.warning(f"MAC ya existe en whitelist: {mac_normalized}")
        return False, f"Error: MAC {mac_normalized} ya está en la whitelist"
    
    # Agregar a whitelist
    whitelist.append(mac_normalized)
    vlan_1_cfg["mac_whitelist"] = whitelist
    
    # Guardar configuración
    _save_ebtables_config(ebtables_cfg)
    
    # Aplicar reglas SOLO si el módulo está activo
    if module_active:
        wan_iface = ebtables_cfg.get("wan_interface", "")
        if not _apply_mac_whitelist_rules(1, wan_iface, whitelist):
            logger.warning(f"Warning: MAC agregada pero no se pudieron aplicar reglas de ebtables")
    
    logger.info(f"MAC {mac_normalized} agregada a whitelist de VLAN 1")
    log_action("ebtables", f"add_mac {mac_normalized} - SUCCESS")
    
    status_msg = f"✅ MAC {mac_normalized} agregada a la whitelist\nTotal de MACs: {len(whitelist)}"
    if not module_active:
        status_msg += "\n⚠️ Cambios se aplicarán cuando inicie el módulo"
    return True, status_msg


def remove_mac(params: Dict[str, Any]) -> Tuple[bool, str]:
    """Remover una dirección MAC de la whitelist de VLAN 1.
    
    Args:
        params: Diccionario con 'mac' (formato XX:XX:XX:XX:XX:XX)
    
    Returns:
        (True, mensaje) si éxito, (False, error) si falla
    """
    _ensure_dirs()
    
    if not params or "mac" not in params:
        return False, "Error: Falta parámetro 'mac'"
    
    mac = params.get("mac", "").strip()
    
    if not mac:
        return False, "Error: MAC requerida"
    
    # Validar formato de MAC
    if not _validate_mac_address(mac):
        logger.error(f"MAC inválida: {mac}")
        return False, f"Error: Formato de MAC inválido: {mac}\nUse formato: XX:XX:XX:XX:XX:XX"
    
    # Normalizar MAC
    mac_normalized = _normalize_mac_address(mac)
    
    # Cargar configuración
    ebtables_cfg = _load_ebtables_config()
    module_active = ebtables_cfg.get("status", 0) == 1
    
    # Verificar que VLAN 1 existe
    if "vlans" not in ebtables_cfg or "1" not in ebtables_cfg["vlans"]:
        return False, "Error: VLAN 1 no está configurada"
    
    vlan_1_cfg = ebtables_cfg["vlans"]["1"]
    whitelist = vlan_1_cfg.get("mac_whitelist", [])
    
    # Verificar que existe
    if mac_normalized not in whitelist:
        logger.warning(f"MAC no encontrada en whitelist: {mac_normalized}")
        return False, f"Error: MAC {mac_normalized} no está en la whitelist"
    
    # Remover de whitelist
    whitelist.remove(mac_normalized)
    vlan_1_cfg["mac_whitelist"] = whitelist
    
    # Guardar configuración
    _save_ebtables_config(ebtables_cfg)
    
    # Aplicar reglas SOLO si el módulo está activo
    if module_active:
        wan_iface = ebtables_cfg.get("wan_interface", "")
        if not _apply_mac_whitelist_rules(1, wan_iface, whitelist):
            logger.warning(f"Warning: MAC removida pero no se pudieron aplicar reglas de ebtables")
    
    logger.info(f"MAC {mac_normalized} removida de whitelist de VLAN 1")
    log_action("ebtables", f"remove_mac {mac_normalized} - SUCCESS")
    
    status_msg = f"✅ MAC {mac_normalized} removida de la whitelist\nTotal de MACs: {len(whitelist)}"
    if not module_active:
        status_msg += "\n⚠️ Cambios se aplicarán cuando inicie el módulo"
    return True, status_msg


def enable_whitelist(params: Dict[str, Any] = None) -> Tuple[bool, str]:
    """Habilitar la whitelist de MAC para VLAN 1.
    
    Returns:
        (True, mensaje) si éxito, (False, error) si falla
    """
    _ensure_dirs()
    
    # Cargar configuración
    ebtables_cfg = _load_ebtables_config()
    module_active = ebtables_cfg.get("status", 0) == 1
    
    # Asegurar que VLAN 1 existe
    if "vlans" not in ebtables_cfg:
        ebtables_cfg["vlans"] = {}
    if "1" not in ebtables_cfg["vlans"]:
        ebtables_cfg["vlans"]["1"] = {
            "name": "Admin",
            "isolated": False,
            "mac_whitelist_enabled": True,
            "mac_whitelist": []
        }
    
    vlan_1_cfg = ebtables_cfg["vlans"]["1"]
    vlan_1_cfg["mac_whitelist_enabled"] = True
    
    # Guardar configuración
    _save_ebtables_config(ebtables_cfg)
    
    # Aplicar reglas SOLO si el módulo está activo
    if module_active:
        whitelist = vlan_1_cfg.get("mac_whitelist", [])
        wan_iface = ebtables_cfg.get("wan_interface", "")
        if not _apply_mac_whitelist_rules(1, wan_iface, whitelist):
            logger.warning(f"Warning: Whitelist habilitada pero no se pudieron aplicar reglas de ebtables")
    
    logger.info("MAC whitelist habilitada para VLAN 1")
    log_action("ebtables", "enable_whitelist - SUCCESS")
    
    status_msg = "✅ Whitelist de MAC habilitada para VLAN 1"
    if not module_active:
        status_msg += "\n⚠️ Cambios se aplicarán cuando inicie el módulo"
    return True, status_msg


def disable_whitelist(params: Dict[str, Any] = None) -> Tuple[bool, str]:
    """Deshabilitar la whitelist de MAC para VLAN 1.
    
    Returns:
        (True, mensaje) si éxito, (False, error) si falla
    """
    _ensure_dirs()
    
    # Cargar configuración
    ebtables_cfg = _load_ebtables_config()
    module_active = ebtables_cfg.get("status", 0) == 1
    
    # Verificar que VLAN 1 existe
    if "vlans" not in ebtables_cfg or "1" not in ebtables_cfg["vlans"]:
        return False, "Error: VLAN 1 no está configurada"
    
    vlan_1_cfg = ebtables_cfg["vlans"]["1"]
    vlan_1_cfg["mac_whitelist_enabled"] = False
    
    # Guardar configuración
    _save_ebtables_config(ebtables_cfg)
    
    # Remover reglas SOLO si el módulo está activo
    if module_active:
        if not _remove_mac_whitelist_rules(1):
            logger.warning(f"Warning: Whitelist deshabilitada pero no se pudieron remover reglas de ebtables")
    
    logger.info("MAC whitelist deshabilitada para VLAN 1")
    log_action("ebtables", "disable_whitelist - SUCCESS")
    
    status_msg = "⚠️ Whitelist de MAC deshabilitada para VLAN 1 (todo el tráfico MAC permitido)"
    if not module_active:
        status_msg += "\n⚠️ Cambios se aplicarán cuando inicie el módulo"
    return True, status_msg


def show_whitelist(params: Dict[str, Any] = None) -> Tuple[bool, str]:
    """Mostrar la whitelist de MAC de VLAN 1.
    
    Returns:
        (True, mensaje con lista de MACs)
    """
    _ensure_dirs()
    
    # Cargar configuración
    ebtables_cfg = _load_ebtables_config()
    
    # Verificar que VLAN 1 existe
    if "vlans" not in ebtables_cfg or "1" not in ebtables_cfg["vlans"]:
        return True, "Whitelist de MAC VLAN 1: No configurada\nSin MACs configuradas"
    
    vlan_1_cfg = ebtables_cfg["vlans"]["1"]
    whitelist = vlan_1_cfg.get("mac_whitelist", [])
    enabled = vlan_1_cfg.get("mac_whitelist_enabled", True)
    
    status_str = "✅ HABILITADA" if enabled else "⚠️ DESHABILITADA"
    
    if not whitelist:
        message = f"Whitelist de MAC VLAN 1: {status_str}\nSin MACs configuradas"
    else:
        mac_list = "\n".join([f"  • {mac}" for mac in whitelist])
        message = f"Whitelist de MAC VLAN 1: {status_str}\nTotal: {len(whitelist)} MACs\n\n{mac_list}"
    
    logger.info("Show whitelist VLAN 1")
    return True, message


def config(params: Dict[str, Any] = None) -> Tuple[bool, str]:
    """DEPRECATED: Usar funciones específicas (add_mac, remove_mac, enable_whitelist, etc.)
    
    Esta función mantiene compatibilidad con código antiguo.
    """
    if not params:
        return False, "Error: Parámetros requeridos"
    
    action = params.get("action")
    
    if action == "add_mac":
        return add_mac(params)
    elif action == "remove_mac":
        return remove_mac(params)
    elif action == "enable_whitelist":
        return enable_whitelist(params)
    elif action == "disable_whitelist":
        return disable_whitelist(params)
    elif action == "show_whitelist":
        return show_whitelist(params)
    else:
        logger.error(f"Acción desconocida en config: {action}")
        return False, f"Error: Acción desconocida: {action}"


# =============================================================================
# ACCIONES PERMITIDAS
# =============================================================================

ALLOWED_ACTIONS = {
    "start": start,
    "stop": stop,
    "restart": restart,
    "status": status,
    "isolate": isolate,
    "unisolate": unisolate,
    # MAC Whitelist (funcionalidad principal)
    "add_mac": add_mac,
    "remove_mac": remove_mac,
    "enable_whitelist": enable_whitelist,
    "disable_whitelist": disable_whitelist,
    "show_whitelist": show_whitelist,
    # Compatibilidad con código antiguo
    "config": config,
}

