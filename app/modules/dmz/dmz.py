
# app/core/dmz.py
# Módulo de DMZ - Arquitectura jerárquica con cadenas por VLAN
# VERSION 2.0 - Refactorización completa

import os
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
import logging
from typing import Dict, Any, Tuple
from ...utils.global_helpers import run_command
from ...utils.global_helpers import module_helpers as mh, io_helpers as ioh
from .helpers import (
    ensure_dirs, write_log, load_config, save_config,
    load_wan_config, load_firewall_config, load_vlans_config, get_vlan_from_ip,
    ensure_prerouting_protection_chain, ensure_prerouting_vlan_chain, remove_prerouting_vlan_chain,
    add_forward_return_rule, remove_forward_return_rule,
    check_wan_configured, validate_destination
)

# Configurar logging
logger = logging.getLogger(__name__)

# Rutas de configuración
# BASE_DIR ya está definido correctamente arriba (line 7)
CONFIG_FILE = os.path.join(BASE_DIR, "config", "dmz", "dmz.json")
WAN_CONFIG_FILE = os.path.join(BASE_DIR, "config", "wan", "wan.json")
VLANS_CONFIG_FILE = os.path.join(BASE_DIR, "config", "vlans", "vlans.json")
FIREWALL_CONFIG_FILE = os.path.join(BASE_DIR, "config", "firewall", "firewall.json")
LOG_FILE = os.path.join(BASE_DIR, "logs", "dmz", "actions.log")


# =============================================================================
# UTILIDADES BÁSICAS
# =============================================================================

# Alias helpers para compatibilidad
_run_command = lambda cmd: run_command(cmd)
_ensure_dirs = ensure_dirs
_write_log = write_log
_load_config = load_config
_save_config = save_config
_load_wan_config = load_wan_config
_load_firewall_config = load_firewall_config
_load_vlans_config = load_vlans_config
_get_vlan_from_ip = get_vlan_from_ip
_ensure_prerouting_protection_chain = ensure_prerouting_protection_chain
_ensure_prerouting_vlan_chain = ensure_prerouting_vlan_chain
_remove_prerouting_vlan_chain = remove_prerouting_vlan_chain
_add_forward_return_rule = add_forward_return_rule
_remove_forward_return_rule = remove_forward_return_rule
_check_wan_configured = check_wan_configured
_validate_destination = validate_destination


# =============================================================================
# FUNCIONES PRINCIPALES
# =============================================================================

def start(params: Dict[str, Any] = None) -> Tuple[bool, str]:
    """Iniciar DMZ - Aplicar reglas DNAT en cadenas PREROUTING_VLAN_X."""
    logger.info("=== INICIO: dmz start ===")
    _ensure_dirs()
    
    # Asegurar que existe la cadena de protección para aislamiento
    mh.ensure_global_chains(); _ensure_prerouting_protection_chain()
    
    # Verificar dependencias
    deps_ok, deps_msg = mh.check_module_dependencies(BASE_DIR, "dmz")
    if not deps_ok:
        logger.error(f"Dependencias no satisfechas: {deps_msg}")
        _write_log(f"❌ {deps_msg}")
        return False, deps_msg
    
    # Obtener interfaz WAN para logs/info
    _, wan_interface = _check_wan_configured()
    
    # Cargar configuración
    dmz_cfg = _load_config()
    destinations = dmz_cfg.get("destinations", [])
    
    if not destinations:
        msg = "No hay destinos DMZ configurados. Agregue destinos primero."
        logger.warning(msg)
        _write_log(f"⚠️ {msg}")
        return False, msg
    
    _write_log("=" * 80)
    _write_log(f"🚀 Iniciando DMZ con {len(destinations)} destino(s)")
    _write_log(f"🌐 Interfaz WAN: {wan_interface}")
    
    results = []
    errors = []
    
    # Agrupar destinos por VLAN
    destinations_by_vlan = {}
    for dest in destinations:
        ip = dest["ip"]
        vlan_id = _get_vlan_from_ip(ip)
        
        if vlan_id is None:
            errors.append(f"{ip} - no se pudo determinar VLAN")
            continue
        
        if vlan_id not in destinations_by_vlan:
            destinations_by_vlan[vlan_id] = []
        destinations_by_vlan[vlan_id].append(dest)
    
    # Procesar cada VLAN
    for vlan_id, vlan_destinations in destinations_by_vlan.items():
        logger.info(f"Procesando VLAN {vlan_id} con {len(vlan_destinations)} destino(s) DMZ")
        
        # Crear cadena PREROUTING_VLAN_X
        if not _ensure_prerouting_vlan_chain(vlan_id):
            errors.append(f"VLAN {vlan_id}: Error creando cadena PREROUTING")
            continue
        
        chain_name = "JSB_DMZ_STATS"
        
        # Aplicar reglas DNAT para cada destino
        for dest in vlan_destinations:
            ip = dest["ip"]
            port = dest["port"]
            protocol = dest["protocol"]
            
            # Validar destino
            valid, error_msg = _validate_destination(ip, port, protocol)
            if not valid:
                errors.append(f"{ip}:{port}/{protocol} - {error_msg}")
                _write_log(f"❌ {ip}:{port}/{protocol} - {error_msg}")
                continue
            
            # Verificar si la regla DNAT ya existe
            check_cmd = [
                "/usr/sbin/iptables", "-t", "nat", "-C", chain_name,
                "-i", wan_interface, "-p", protocol, "--dport", str(port),
                "-j", "DNAT", "--to-destination", ip
            ]
            
            success, _ = _run_command(check_cmd)
            
            if success:
                logger.info(f"Regla DNAT {ip}:{port}/{protocol} ya existe en {chain_name}")
                results.append(f"{ip}:{port}/{protocol} - ya existía")
                continue
            
            # Añadir regla LOG y DNAT
            _run_command([
                "/usr/sbin/iptables", "-t", "nat", "-A", chain_name,
                "-i", wan_interface, "-p", protocol, "--dport", str(port),
                "-j", "LOG", "--log-prefix", f"[JSB-DMZ-DNAT] {ip}:{port} "
            ])
            cmd = [
                "/usr/sbin/iptables", "-t", "nat", "-A", chain_name,
                "-i", wan_interface, "-p", protocol, "--dport", str(port),
                "-j", "DNAT", "--to-destination", ip
            ]
            
            success, output = _run_command(cmd)
            
            if success:
                results.append(f"{ip}:{port}/{protocol} - activado")
                logger.info(f"Regla DNAT {ip}:{port}/{protocol} aplicada en {chain_name}")
                _write_log(f"✅ Regla DNAT aplicada: {ip}:{port}/{protocol} (interfaz: {wan_interface})")
                
                # Añadir regla RETURN en FORWARD_VLAN_X
                if _add_forward_return_rule(vlan_id, ip):
                    _write_log(f"✅ Regla RETURN añadida en FORWARD_VLAN_{vlan_id} para {ip}")
                else:
                    logger.warning(f"No se pudo añadir regla RETURN para {ip} en FORWARD_VLAN_{vlan_id}")
            else:
                errors.append(f"{ip}:{port}/{protocol} - error: {output}")
                logger.error(f"Error aplicando regla DNAT {ip}:{port}/{protocol}: {output}")
                _write_log(f"❌ Error añadiendo regla DNAT {ip}:{port}/{protocol}: {output}")
    
    # Actualizar estado
    dmz_cfg["status"] = 1
    if not _save_config(dmz_cfg):
        _write_log(f"❌ Error guardando configuración en {CONFIG_FILE}")
        logger.error(f"Error guardando configuración en {CONFIG_FILE}")
        return False, "Error guardando configuración en disco"
    
    msg = "DMZ iniciado:\n" + "\n".join(results)
    if errors:
        msg += "\n\nErrores:\n" + "\n".join(errors)
        _write_log(f"⚠️ DMZ iniciado con errores: {'; '.join(errors)}")
        _write_log("=" * 80 + "\n")
    else:
        _write_log(f"✅ DMZ iniciado correctamente: {'; '.join(results)}")
        _write_log("=" * 80 + "\n")
    
    logger.info("=== FIN: dmz start ===")
    return len(errors) == 0, msg


def stop(params: Dict[str, Any] = None) -> Tuple[bool, str]:
    """Detener DMZ - Eliminar reglas DNAT y cadenas PREROUTING_VLAN_X."""
    logger.info("=== INICIO: dmz stop ===")
    _ensure_dirs()
    
    dmz_cfg = _load_config()
    destinations = dmz_cfg.get("destinations", [])
    
    if not destinations:
        msg = "No hay destinos DMZ configurados"
        logger.warning(msg)
        return True, msg
    
    _write_log("=" * 80)
    _write_log(f"🛑 Deteniendo DMZ - eliminando {len(destinations)} destino(s)")
    
    results = []
    
    # Agrupar destinos por VLAN
    destinations_by_vlan = {}
    for dest in destinations:
        ip = dest["ip"]
        vlan_id = _get_vlan_from_ip(ip)
        
        if vlan_id is None:
            continue
        
        if vlan_id not in destinations_by_vlan:
            destinations_by_vlan[vlan_id] = []
        destinations_by_vlan[vlan_id].append(dest)
    
    # Eliminar reglas RETURN de FORWARD_VLAN_X
    for vlan_id, vlan_destinations in destinations_by_vlan.items():
        for dest in vlan_destinations:
            ip = dest["ip"]
            _remove_forward_return_rule(vlan_id, ip)
    
    # Eliminar reglas de aislamiento (INPUT y JSB_DMZ_ISOLATE) para hosts aislados
    isolated_hosts = [dest["ip"] for dest in destinations if dest.get("isolated", False)]
    if isolated_hosts:
        logger.info(f"Eliminando reglas de aislamiento para {len(isolated_hosts)} host(s)")
        for ip in isolated_hosts:
            # Eliminar regla RETURN de JSB_DMZ_ISOLATE
            check_prerouting = ["/usr/sbin/iptables", "-t", "nat", "-C", "JSB_DMZ_ISOLATE", "-d", ip, "-j", "RETURN"]
            success, _ = _run_command(check_prerouting)
            if success:
                _run_command(["/usr/sbin/iptables", "-t", "nat", "-D", "JSB_DMZ_ISOLATE", "-d", ip, "-j", "RETURN"])
                logger.info(f"Regla de aislamiento eliminada de JSB_DMZ_ISOLATE para {ip}")
            
            # Eliminar regla DROP de JSB_FW_RESTRICT
            check_input = ["/usr/sbin/iptables", "-C", "JSB_FW_RESTRICT", "-s", ip, "-j", "DROP"]
            success, _ = _run_command(check_input)
            if success:
                _run_command(["/usr/sbin/iptables", "-D", "JSB_FW_RESTRICT", "-s", ip, "-j", "DROP"])
                logger.info(f"Regla de aislamiento eliminada de JSB_FW_RESTRICT para {ip}")
        
        results.append(f"Reglas de aislamiento eliminadas para {len(isolated_hosts)} host(s)")
    
    # Eliminar cadenas PREROUTING_VLAN_X
    for vlan_id in destinations_by_vlan.keys():
        _remove_prerouting_vlan_chain(vlan_id)
        results.append(f"VLAN {vlan_id}: Cadena PREROUTING eliminada")
        logger.info(f"Cadena PREROUTING_VLAN_{vlan_id} eliminada")
    
    # Actualizar estado
    dmz_cfg["status"] = 0
    if not _save_config(dmz_cfg):
        _write_log(f"❌ Error guardando configuración en {CONFIG_FILE}")
        logger.error(f"Error guardando configuración en {CONFIG_FILE}")
        return False, "Error guardando configuración en disco"
    
    msg = "DMZ detenido:\n" + "\n".join(results)
    _write_log(f"✅ DMZ detenido correctamente")
    _write_log("=" * 80 + "\n")
    
    logger.info("=== FIN: dmz stop ===")
    return True, msg


def restart(params: Dict[str, Any] = None) -> Tuple[bool, str]:
    """Reiniciar DMZ."""
    logger.info("=== INICIO: dmz restart ===")
    
    _, stop_msg = stop(params)
    start_success, start_msg = start(params)
    
    msg = f"STOP:\n{stop_msg}\n\nSTART:\n{start_msg}"
    logger.info("=== FIN: dmz restart ===")
    
    return start_success, msg


def status(params: Dict[str, Any] = None) -> Tuple[bool, str]:
    """Obtener estado de DMZ."""
    logger.info("=== INICIO: dmz status ===")
    
    dmz_cfg = _load_config()
    dmz_status = dmz_cfg.get("status", 0)
    destinations = dmz_cfg.get("destinations", [])
    
    lines = ["Estado de DMZ:", "=" * 50]
    lines.append(f"Estado: {'ACTIVO' if dmz_status == 1 else 'INACTIVO'}")
    lines.append(f"Destinos configurados: {len(destinations)}")
    
    if destinations:
        lines.append("\nDestinos:")
        for dest in destinations:
            ip = dest["ip"]
            port = dest["port"]
            protocol = dest["protocol"]
            vlan_id = _get_vlan_from_ip(ip)
            lines.append(f"  - {ip}:{port}/{protocol} (VLAN {vlan_id})")
    
    msg = "\n".join(lines)
    logger.info("=== FIN: dmz status ===")
    return True, msg


def config(params: Dict[str, Any] = None) -> Tuple[bool, str]:
    """Configurar DMZ (placeholder para interfaz web)."""
    logger.info("Config llamado desde interfaz web")
    return True, "Use la interfaz web para configurar DMZ"


# =============================================================================
# GESTIÓN DE DESTINOS DMZ
# =============================================================================

def add_destination(params: Dict[str, Any] = None) -> Tuple[bool, str]:
    """Añadir un nuevo destino DMZ."""
    logger.info("=== INICIO: add_destination ===")
    
    if not params:
        return False, "Error: Parámetros requeridos"
    
    ip = params.get("ip", "").strip()
    port = params.get("port")
    protocol = params.get("protocol", "tcp").lower()
    
    if not ip or not port:
        return False, "Error: IP y puerto son requeridos"
    
    try:
        port = int(port)
    except (ValueError, TypeError):
        return False, f"Error: Puerto debe ser un número entero"
    
    # Validar destino
    valid, error_msg = _validate_destination(ip, port, protocol)
    if not valid:
        return False, error_msg
    
    # Verificar duplicados
    dmz_cfg = _load_config()
    destinations = dmz_cfg.get("destinations", [])
    
    for dest in destinations:
        if dest["ip"] == ip and dest["port"] == port and dest["protocol"] == protocol:
            return False, f"El destino {ip}:{port}/{protocol} ya existe"
    
    # Verificar si el puerto y protocolo ya están en uso por otro destino
    for dest in destinations:
        if dest["port"] == port and dest["protocol"] == protocol and dest["ip"] != ip:
            return False, f"Error: El puerto {port}/{protocol} ya está en uso por {dest['ip']}. Cada puerto solo puede redirigirse a un único destino."
    
    # Añadir destino
    destinations.append({
        "ip": ip,
        "isolated": False,
        "port": port,
        "protocol": protocol
    })
    
    dmz_cfg["destinations"] = destinations
    if not _save_config(dmz_cfg):
        _write_log(f"❌ Error guardando configuración en {CONFIG_FILE}")
        logger.error(f"Error guardando configuración en {CONFIG_FILE}")
        return False, "Error guardando configuración en disco"
    
    msg = f"Destino DMZ añadido: {ip}:{port}/{protocol}"
    _write_log(f"➕ {msg}")
    
    # Si DMZ está activo, aplicar regla inmediatamente
    if dmz_cfg.get("status", 0) == 1:
        logger.info("DMZ activo, aplicando regla inmediatamente")
        restart()
    
    logger.info("=== FIN: add_destination ===")
    return True, msg


def remove_destination(params: Dict[str, Any] = None) -> Tuple[bool, str]:
    """Eliminar un destino DMZ."""
    logger.info("=== INICIO: remove_destination ===")
    
    if not params:
        return False, "Error: Parámetros requeridos"
    
    ip = params.get("ip", "").strip()
    port = params.get("port")
    protocol = params.get("protocol", "tcp").lower()
    
    if not ip or not port:
        return False, "Error: IP y puerto son requeridos"
    
    try:
        port = int(port)
    except (ValueError, TypeError):
        return False, f"Error: Puerto debe ser un número entero"
    
    # Buscar y eliminar destino
    dmz_cfg = _load_config()
    destinations = dmz_cfg.get("destinations", [])
    
    found = False
    was_isolated = False
    for i, dest in enumerate(destinations):
        if dest["ip"] == ip and dest["port"] == port and dest["protocol"] == protocol:
            was_isolated = dest.get("isolated", False)
            destinations.pop(i)
            found = True
            break
    
    if not found:
        return False, f"Destino {ip}:{port}/{protocol} no encontrado"
    
    # Si el destino estaba aislado, eliminar reglas de aislamiento
    if was_isolated:
        logger.info(f"Destino {ip} estaba aislado, eliminando reglas de aislamiento")
        
        # Eliminar regla RETURN de JSB_DMZ_ISOLATE
        check_prerouting = ["/usr/sbin/iptables", "-t", "nat", "-C", "JSB_DMZ_ISOLATE", "-d", ip, "-j", "RETURN"]
        success, _ = _run_command(check_prerouting)
        if success:
            _run_command(["/usr/sbin/iptables", "-t", "nat", "-D", "JSB_DMZ_ISOLATE", "-d", ip, "-j", "RETURN"])
            logger.info(f"Regla de aislamiento eliminada de JSB_DMZ_ISOLATE para {ip}")
            _write_log(f"🔓 Regla de aislamiento eliminada de JSB_DMZ_ISOLATE para {ip}")
        
        # Eliminar regla DROP de JSB_FW_RESTRICT
        check_input = ["/usr/sbin/iptables", "-C", "JSB_FW_RESTRICT", "-s", ip, "-j", "DROP"]
        success, _ = _run_command(check_input)
        if success:
            _run_command(["/usr/sbin/iptables", "-D", "JSB_FW_RESTRICT", "-s", ip, "-j", "DROP"])
            logger.info(f"Regla de aislamiento eliminada de JSB_FW_RESTRICT para {ip}")
            _write_log(f"🔓 Regla de aislamiento eliminada de JSB_FW_RESTRICT para {ip}")
    
    dmz_cfg["destinations"] = destinations
    if not _save_config(dmz_cfg):
        _write_log(f"❌ Error guardando configuración en {CONFIG_FILE}")
        logger.error(f"Error guardando configuración en {CONFIG_FILE}")
        return False, "Error guardando configuración en disco"
    
    msg = f"Destino DMZ eliminado: {ip}:{port}/{protocol}"
    if was_isolated:
        msg += " (reglas de aislamiento también eliminadas)"
    _write_log(f"➖ {msg}")
    
    # Si DMZ está activo, eliminar regla inmediatamente
    if dmz_cfg.get("status", 0) == 1:
        logger.info("DMZ activo, eliminando regla inmediatamente")
        restart()
    
    logger.info("=== FIN: remove_destination ===")
    return True, msg


def update_destination(params: Dict[str, Any] = None) -> Tuple[bool, str]:
    """Actualizar un destino DMZ existente."""
    logger.info("=== INICIO: update_destination ===")
    
    if not params:
        return False, "Error: Parámetros requeridos"
    
    old_ip = params.get("old_ip", "").strip()
    old_port = params.get("old_port")
    old_protocol = params.get("old_protocol", "tcp").lower()
    
    new_ip = params.get("new_ip", "").strip()
    new_port = params.get("new_port")
    new_protocol = params.get("new_protocol", "tcp").lower()
    
    if not all([old_ip, old_port, new_ip, new_port]):
        return False, "Error: Todos los parámetros son requeridos"
    
    try:
        old_port = int(old_port)
        new_port = int(new_port)
    except (ValueError, TypeError):
        return False, f"Error: Puertos deben ser números enteros"
    
    # Validar nuevo destino
    valid, error_msg = _validate_destination(new_ip, new_port, new_protocol)
    if not valid:
        return False, error_msg
    
    # Buscar y actualizar destino
    dmz_cfg = _load_config()
    destinations = dmz_cfg.get("destinations", [])
    
    # Verificar que el nuevo puerto no esté en uso por otro destino
    for dest in destinations:
        # Si es un destino diferente (no el que estamos actualizando)
        if not (dest["ip"] == old_ip and dest["port"] == old_port and dest["protocol"] == old_protocol):
            # Y usa el mismo puerto/protocolo
            if dest["port"] == new_port and dest["protocol"] == new_protocol:
                return False, f"Error: El puerto {new_port}/{new_protocol} ya está en uso por {dest['ip']}. Cada puerto solo puede redirigirse a un único destino."
    
    found = False
    for dest in destinations:
        if dest["ip"] == old_ip and dest["port"] == old_port and dest["protocol"] == old_protocol:
            dest["ip"] = new_ip
            dest["port"] = new_port
            dest["protocol"] = new_protocol
            found = True
            break
    
    if not found:
        return False, f"Destino {old_ip}:{old_port}/{old_protocol} no encontrado"
    
    if not _save_config(dmz_cfg):
        _write_log(f"❌ Error guardando configuración en {CONFIG_FILE}")
        logger.error(f"Error guardando configuración en {CONFIG_FILE}")
        return False, "Error guardando configuración en disco"
    
    msg = f"Destino DMZ actualizado: {old_ip}:{old_port}/{old_protocol} → {new_ip}:{new_port}/{new_protocol}"
    _write_log(f"✏️ {msg}")
    
    # Si DMZ está activo, reaplicar reglas
    if dmz_cfg.get("status", 0) == 1:
        logger.info("DMZ activo, reaplicando reglas")
        restart()
    
    logger.info("=== FIN: update_destination ===")
    return True, msg


def isolate_dmz_host(params: Dict[str, Any] = None) -> Tuple[bool, str]:
    """Aislar un host DMZ específico bloqueando todo su tráfico DNAT.
    
    El aislamiento tiene PRIORIDAD MÁXIMA:
    - Inserta regla DROP en JSB_DMZ_ISOLATE (tabla NAT)
    - Bloquea el tráfico WAN->DMZ antes de que se aplique DNAT
    - También bloquea en INPUT el tráfico desde el host hacia el router
    """
    logger.info("=== INICIO: isolate_dmz_host ===")
    
    if not params or "ip" not in params:
        return False, "Error: Se requiere parámetro 'ip'"
    
    ip = params["ip"].strip()
    
    # Validar que la IP es válida y pertenece a una VLAN configurada
    vlan_id = _get_vlan_from_ip(ip)
    if not vlan_id:
        vlans_cfg = _load_vlans_config()
        vlans = vlans_cfg.get("vlans", []) if vlans_cfg else []
        if vlans:
            vlan_networks = ", ".join([v.get("ip_network", "N/A") for v in vlans])
            return False, f"IP {ip} no está en ninguna VLAN configurada. VLANs disponibles: {vlan_networks}"
        else:
            return False, f"IP {ip} no está en ninguna VLAN. Configure VLANs primero."
    
    vlans_cfg = _load_vlans_config()
    if not vlans_cfg:
        return False, "Error: No se pudo cargar configuración de VLANs"
    
    vlan_found = False
    for vlan in vlans_cfg.get("vlans", []):
        if vlan["id"] == vlan_id:
            vlan_found = True
            break
    
    if not vlan_found:
        return False, f"VLAN {vlan_id} no existe en el sistema"
    
    # Verificar que la IP está en dmz.json
    dmz_cfg = _load_config()
    destinations = dmz_cfg.get("destinations", [])
    
    ip_in_dmz = False
    for dest in destinations:
        if dest["ip"] == ip:
            ip_in_dmz = True
            # Marcar como aislado
            if "isolated" not in dest or not dest["isolated"]:
                dest["isolated"] = True
            break
    
    if not ip_in_dmz:
        return False, f"IP {ip} no está configurada en DMZ. Configure el destino primero."
    
    # Asegurar que existe la cadena JSB_DMZ_ISOLATE
    mh.ensure_global_chains(); _ensure_prerouting_protection_chain()
    
    # Verificar si ya existe regla de aislamiento en PREROUTING (NAT)
    cmd_check_prerouting = [
        "/usr/sbin/iptables",
        "-t", "nat",
        "-C", "JSB_DMZ_ISOLATE",
        "-d", ip,
        "-j", "RETURN"
    ]
    already_isolated_prerouting, _ = _run_command(cmd_check_prerouting)
    
    # Verificar si ya existe regla de aislamiento en JSB_FW_RESTRICT (bloquea tráfico desde el host hacia el router)
    cmd_check_input_src = [
        "/usr/sbin/iptables",
        "-C", "JSB_FW_RESTRICT",
        "-s", ip,
        "-j", "DROP"
    ]
    already_isolated_input, _ = _run_command(cmd_check_input_src)
    
    if already_isolated_prerouting and already_isolated_input:
        if not _save_config(dmz_cfg):  # Guardar el campo isolated=True
            _write_log(f"❌ Error guardando configuración en {CONFIG_FILE}")
            logger.error(f"Error guardando configuración en {CONFIG_FILE}")
            return False, "Error guardando configuración en disco"
        return True, f"Host {ip} ya está aislado"
    
    # Insertar regla RETURN en JSB_DMZ_ISOLATE (evita que se aplique DNAT)
    # RETURN hace que el paquete salga de esta cadena sin continuar, impidiendo el port forwarding
    if not already_isolated_prerouting:
        cmd_isolate_prerouting = [
            "/usr/sbin/iptables",
            "-t", "nat",
            "-I", "JSB_DMZ_ISOLATE", "1",  # Posición 1 = máxima prioridad
            "-d", ip,
            "-j", "RETURN"
        ]
        
        success, output = _run_command(cmd_isolate_prerouting)
        if not success:
            return False, f"Error al aislar host {ip} en PREROUTING: {output}"
    
    # Insertar regla DROP en JSB_FW_RESTRICT (bloquear tráfico DESDE el host hacia el router)
    if not already_isolated_input:
        cmd_isolate_input = [
            "/usr/sbin/iptables",
            "-I", "JSB_FW_RESTRICT", "1",  # Posición 1 = máxima prioridad
            "-s", ip,
            "-j", "DROP"
        ]
        
        success, output = _run_command(cmd_isolate_input)
        if not success:
            # Intentar limpiar la regla de PREROUTING si JSB_FW_RESTRICT falla
            if not already_isolated_prerouting:
                _run_command(["/usr/sbin/iptables", "-t", "nat", "-D", "JSB_DMZ_ISOLATE", "-d", ip, "-j", "RETURN"])
            return False, f"Error al aislar host {ip} en JSB_FW_RESTRICT: {output}"
    
    # Guardar configuración con campo isolated
    if not _save_config(dmz_cfg):
        _write_log(f"❌ Error guardando configuración en {CONFIG_FILE}")
        logger.error(f"Error guardando configuración en {CONFIG_FILE}")
        return False, "Error guardando configuración en disco"
    
    msg = f"Host DMZ {ip} aislado correctamente (RETURN en JSB_DMZ_ISOLATE + DROP en JSB_FW_RESTRICT)"
    _write_log(f"✅ {msg}")
    logger.info(f"Host {ip} aislado correctamente: PREROUTING impide DNAT, JSB_FW_RESTRICT bloquea salida al router")
    logger.info("=== FIN: isolate_dmz_host ===" )
    
    return True, msg


def unisolate_dmz_host(params: Dict[str, Any] = None) -> Tuple[bool, str]:
    """Desaislar un host DMZ específico restaurando su tráfico DNAT."""
    logger.info("=== INICIO: unisolate_dmz_host ===")
    
    if not params or "ip" not in params:
        return False, "Error: Se requiere parámetro 'ip'"
    
    ip = params["ip"].strip()
    
    # Verificar que la IP está en dmz.json
    dmz_cfg = _load_config()
    destinations = dmz_cfg.get("destinations", [])
    
    ip_in_dmz = False
    for dest in destinations:
        if dest["ip"] == ip:
            ip_in_dmz = True
            # Desmarcar como aislado
            dest["isolated"] = False
            break
    
    if not ip_in_dmz:
        return False, f"IP {ip} no está configurada en DMZ"
    
    # Verificar y eliminar regla de JSB_DMZ_ISOLATE (NAT)
    cmd_check_prerouting = [
        "/usr/sbin/iptables",
        "-t", "nat",
        "-C", "JSB_DMZ_ISOLATE",
        "-d", ip,
        "-j", "RETURN"
    ]
    prerouting_exists, _ = _run_command(cmd_check_prerouting)
    
    # Verificar y eliminar regla de JSB_FW_RESTRICT
    cmd_check_input = [
        "/usr/sbin/iptables",
        "-C", "JSB_FW_RESTRICT",
        "-s", ip,
        "-j", "DROP"
    ]
    input_exists, _ = _run_command(cmd_check_input)
    
    if not prerouting_exists and not input_exists:
        if not _save_config(dmz_cfg):  # Guardar el campo isolated=False
            _write_log(f"❌ Error guardando configuración en {CONFIG_FILE}")
            logger.error(f"Error guardando configuración en {CONFIG_FILE}")
            return False, "Error guardando configuración en disco"
        return True, f"Host {ip} no estaba aislado"
    
    # Eliminar de JSB_DMZ_ISOLATE
    if prerouting_exists:
        cmd_remove_prerouting = [
            "/usr/sbin/iptables",
            "-t", "nat",
            "-D", "JSB_DMZ_ISOLATE",
            "-d", ip,
            "-j", "RETURN"
        ]
        success, output = _run_command(cmd_remove_prerouting)
        if not success:
            return False, f"Error eliminando aislamiento de {ip} en PREROUTING: {output}"
    
    # Eliminar de JSB_FW_RESTRICT
    if input_exists:
        cmd_remove_input = [
            "/usr/sbin/iptables",
            "-D", "JSB_FW_RESTRICT",
            "-s", ip,
            "-j", "DROP"
        ]
        success, output = _run_command(cmd_remove_input)
        if not success:
            return False, f"Error eliminando aislamiento de {ip} en JSB_FW_RESTRICT: {output}"
    
    # Guardar configuración con campo isolated=False
    if not _save_config(dmz_cfg):
        _write_log(f"❌ Error guardando configuración en {CONFIG_FILE}")
        logger.error(f"Error guardando configuración en {CONFIG_FILE}")
        return False, "Error guardando configuración en disco"
    
    msg = f"Aislamiento de host DMZ {ip} eliminado correctamente (JSB_DMZ_ISOLATE + JSB_FW_RESTRICT)"
    _write_log(f"🔓 {msg}")
    logger.info(f"Aislamiento de host {ip} eliminado de JSB_DMZ_ISOLATE e JSB_FW_RESTRICT")
    logger.info("=== FIN: unisolate_dmz_host ===")
    
    return True, msg


# =============================================================================
# WHITELIST DE ACCIONES PERMITIDAS
# =============================================================================


def traffic_log(params: Dict[str, Any]) -> Tuple[bool, str]:
    status_val = params.get("status", "on")
    # Persistence
    cfg = load_json_config(CONFIG_FILE) if "load_json_config" in globals() else _load_config() if "_load_config" in globals() else {}
    if cfg:
        cfg["traffic_log"] = (status_val == "on")
        if "save_json_config" in globals():
            save_json_config(CONFIG_FILE, cfg)
        elif "_save_config" in globals():
            _save_config(cfg)
    
    ioh.log_action(os.path.basename(os.path.dirname(__file__)), f"Traffic Log set to {status_val}")
    return True, f"Log de tráfico configurado: {status_val}"

ALLOWED_ACTIONS = {
    "traffic_log": traffic_log,
    "start": start,
    "stop": stop,
    "restart": restart,
    "status": status,
    "add_destination": add_destination,
    "remove_destination": remove_destination,
    "update_destination": update_destination,
    "isolate_dmz_host": isolate_dmz_host,
    "unisolate_dmz_host": unisolate_dmz_host,
    # Alias para CLI
    "config": add_destination,  # CLI: dmz config {...}
    "eliminar": remove_destination,  # CLI: dmz eliminar {...}
    "isolate": isolate_dmz_host,
    "unisolate": unisolate_dmz_host,
}
