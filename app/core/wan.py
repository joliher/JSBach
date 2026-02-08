# app/core/wan.py

import asyncio
import ipaddress
import os
from typing import Dict, Any, Tuple
from ..utils.global_functions import create_module_config_directory, create_module_log_directory
from ..utils.validators import validate_ip_address, validate_interface_name
from ..utils.helpers import (
    load_json_config, save_json_config, update_module_status,
    run_command, validate_interface_name as validate_iface
)
from .helpers import verify_wan_status, verify_dhcp_assignment

# Config file in V4 structure
CONFIG_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "config", "wan", "wan.json")
)

# Alias helpers para compatibilidad
_load_config = lambda: load_json_config(CONFIG_FILE)
_run_command = lambda cmd: run_command(cmd)
_update_status = lambda status: update_module_status(CONFIG_FILE, status)

# Aliases para funciones de helpers (compatibilidad con el resto del código)
_verify_wan_status = lambda: verify_wan_status(CONFIG_FILE)
_verify_dhcp_assignment = lambda iface, max_wait=30: verify_dhcp_assignment(iface, CONFIG_FILE, max_wait)


# --------------------------------
# Acciones públicas (Admin API)
# --------------------------------

def start(params: Dict[str, Any] = None) -> Tuple[bool, str]:
    create_module_config_directory("wan")
    create_module_log_directory("wan")
    cfg = _load_config()
    if not cfg:
        return False, "Configuración WAN no encontrada"

    iface = cfg.get("interface")
    mode = cfg.get("mode")
    if not iface or not mode:
        return False, "Configuración WAN incompleta"

    # Verificar que la interfaz existe
    success, _ = _run_command(["/usr/sbin/ip", "link", "show", iface])
    if not success:
        return False, f"La interfaz {iface} no existe"

    try:
        if mode == "dhcp":
            # Lanzar dhcpcd en background (retorna inmediatamente)
            success, msg = _run_command(["/usr/sbin/dhcpcd", "-b", iface])
            if not success:
                return False, f"Error al lanzar DHCP en {iface}: {msg}"
            
            # NO establecer status a 1 aún, esperar a que se cumplan todas las validaciones
            # Limpiar cualquier error previo de DHCP
            cfg = _load_config() or {}
            cfg.pop("dhcp_error", None)
            cfg["status"] = 0  # Estado pendiente hasta que se verifique
            saved = save_json_config(CONFIG_FILE, cfg)
            if not saved:
                # No abortar, pero advertir
                print(f"Advertencia: no se pudo actualizar {CONFIG_FILE} al iniciar DHCP")
            
            # Crear una tarea asyncio que verifique en background si se cumplieron todas las validaciones
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Si ya hay un loop corriendo (ej: en contexto de FastAPI)
                    asyncio.create_task(_verify_dhcp_assignment(iface))
                else:
                    # Sino, crear la tarea en el loop actual
                    loop.create_task(_verify_dhcp_assignment(iface))
            except RuntimeError:
                # Si no hay loop, intentar crear uno nuevo
                try:
                    asyncio.create_task(_verify_dhcp_assignment(iface))
                except:
                    pass  # Si falla, al menos DHCP se inició correctamente
            
            return True, f"DHCP iniciado en {iface} (verificando IP, estado físico y ruta en background)"

        elif mode == "manual":
            ok, err_msg = _start_manual(iface, cfg)
            if not ok:
                _update_status(0)
                return False, err_msg
            # Para modo manual, verificar que se cumplan las validaciones
            is_valid, _ = _verify_wan_status()
            if not is_valid:
                _update_status(0)
                return False, "Configuración manual incompleta: Sin IP, interfaz no está UP o sin ruta por defecto"
            _update_status(1)
        else:
            return False, f"Modo WAN desconocido: {mode}"

        return True, f"WAN iniciada ({mode})"

    except Exception as e:
        _update_status(0)
        return False, str(e)

def stop(params: Dict[str, Any] = None) -> Tuple[bool, str]:
    create_module_config_directory("wan")
    create_module_log_directory("wan")
    cfg = _load_config()
    iface = cfg.get("interface") if cfg else None
    if not iface:
        return False, "Interfaz WAN no definida"

    try:
        # Intentar revertir resoluciones DNS para la interfaz
        _run_command(["/usr/bin/resolvectl", "revert", iface])

        # Intentar bajar la interfaz
        success, msg = _run_command(["/usr/sbin/ip", "link", "set", iface, "down"])
        if not success:
            return False, f"Error al deshabilitar la interfaz {iface}"

        # Limpiar la dirección IP
        success, msg = _run_command(["/usr/sbin/ip", "a", "flush", "dev", iface])
        if not success:
            return False, f"Error al limpiar la dirección IP de la interfaz {iface}"

        # Limpiar las rutas asociadas a la interfaz
        success, msg = _run_command(["/usr/sbin/ip", "r", "flush", "dev", iface])
        if not success:
            return False, f"Error al limpiar las rutas de la interfaz {iface}"

        # Detener el servicio dhcpcd
        _run_command(["/usr/sbin/dhcpcd", "-k", iface])

        # Actualizar el estado
        _update_status(0)

        return True, "WAN detenida exitosamente"
    
    except Exception as e:
        return False, f"Error inesperado al detener WAN: {e}"


def restart(params: Dict[str, Any] = None) -> Tuple[bool, str]:
    ok, msg = stop()
    if not ok:
        return False, msg
    return start()

def status(params: Dict[str, Any] = None) -> Tuple[bool, str]:
    create_module_config_directory("wan")
    create_module_log_directory("wan")
    cfg = _load_config()
    iface = cfg.get("interface") if cfg else None
    if not iface:
        return False, "Interfaz WAN no definida"

    try:
        # Verificar si hay error pendiente de DHCP
        if cfg and cfg.get("dhcp_error"):
            dhcp_error = cfg.get("dhcp_error")
            # Limpiar el error después de reportarlo
            cfg.pop("dhcp_error", None)
            saved = save_json_config(CONFIG_FILE, cfg)
            if not saved:
                print(f"Advertencia: no se pudo limpiar dhcp_error en {CONFIG_FILE}")
            return False, f"Error de DHCP: {dhcp_error}"
        
        # Comprobar si la interfaz existe y su estado
        success, ip_info = _run_command(["/usr/sbin/ip", "a", "show", iface])
        if not success:
            return False, f"La interfaz {iface} no existe"

        # Verificar si la interfaz está UP o DOWN
        is_up = "state UP" in ip_info or ",UP," in ip_info
        interface_status = "🟢 UP (activa)" if is_up else "🔴 DOWN (inactiva)"
        
        # Verificar si tiene IP asignada
        has_ip = "inet " in ip_info
        ip_status = "✅ Tiene IP asignada" if has_ip else "⚠️ Sin IP asignada"
        
        # Obtener rutas
        success, routes = _run_command(["/usr/sbin/ip", "r"])
        if not success:
            routes = "No se pudieron obtener las rutas"
        
        # Verificar si hay ruta por defecto
        has_default_route = "default" in routes
        route_status = "✅ Tiene ruta por defecto" if has_default_route else "⚠️ Sin ruta por defecto"

        status_summary = f"""Estado de WAN:
==================
Interfaz: {iface}
Estado físico: {interface_status}
Estado IP: {ip_status}
Estado rutas: {route_status}

Detalles de la interfaz:
{ip_info}

Tabla de rutas:
{routes}"""

        return True, status_summary
    except Exception as e:
        return False, f"Error obteniendo status: {e}"

def config(params: Dict[str, Any]) -> Tuple[bool, str]:
    create_module_config_directory("wan")
    create_module_log_directory("wan")
    if not params:
        return False, "No se proporcionaron parámetros"

    required = ["mode", "interface"]
    for r in required:
        if not params.get(r):
            return False, f"Falta el parámetro '{r}'"

    # Validar que mode es un valor permitido
    mode = params["mode"]
    allowed_modes = ["manual", "dhcp"]
    if mode not in allowed_modes:
        return False, f"Modo inválido: '{mode}'. Valores permitidos: {', '.join(allowed_modes)}"

    if params["mode"] == "manual":
        for r in ["ip", "mask", "gateway", "dns"]:
            if not params.get(r):
                return False, f"Falta el parámetro '{r}' para modo manual"
        
        # Validar IP
        valid, error = validate_ip_address(params["ip"])
        if not valid:
            return False, f"IP inválida: {error}"
        
        # Validar Gateway
        valid, error = validate_ip_address(params["gateway"])
        if not valid:
            return False, f"Gateway inválido: {error}"
        
        # Validar DNS (puede ser lista o string separado por comas)
        dns = params.get("dns", [])
        if isinstance(dns, str):
            dns = [d.strip() for d in dns.split(",") if d.strip()]
        for dns_ip in dns:
            valid, error = validate_ip_address(dns_ip)
            if not valid:
                return False, f"DNS inválido '{dns_ip}': {error}"

        valid, error = _validate_manual_network(params["ip"], params["mask"], params["gateway"])
        if not valid:
            return False, error

    # Validar nombre de interfaz
    iface = params["interface"]
    valid, error = validate_interface_name(iface)
    if not valid:
        return False, f"Interfaz inválida: {error}"
    
    # Validar que la interfaz existe en el sistema
    success, _ = _run_command(["/usr/sbin/ip", "link", "show", iface])
    if not success:
        return False, f"La interfaz '{iface}' no existe en el sistema. Verifique con 'ip link show'."

    try:
        # Cargar configuración existente para preservar el status
        existing_cfg = _load_config() or {}
        preserved_status = existing_cfg.get("status", 0)

        # Construir nueva configuración evitando mezclar parámetros de modos distintos
        new_cfg = {}
        # Siempre preservar 'interface' y 'mode'
        new_cfg['interface'] = params['interface']
        new_cfg['mode'] = mode

        if mode == 'manual':
            # Incluir solo parámetros manuales y eliminar cualquier clave relacionada con DHCP
            new_cfg['ip'] = params.get('ip')
            new_cfg['mask'] = params.get('mask')
            new_cfg['gateway'] = params.get('gateway')
            # Normalizar dns a string si viene lista
            dns = params.get('dns', [])
            if isinstance(dns, list):
                dns = ",".join(dns)
            new_cfg['dns'] = dns
            # Eliminar indicaciones previas de error DHCP
            if 'dhcp_error' in existing_cfg:
                existing_cfg.pop('dhcp_error', None)
        else:
            # modo == 'dhcp'
            # No conservar parámetros manuales
            # Eliminar cualquier clave manual anterior
            # Mantener claves específicas de DHCP si las hubiera
            if 'dhcp_error' in existing_cfg:
                # mantener dhcp_error solo si existe (será limpia en status cuando corresponda)
                new_cfg['dhcp_error'] = existing_cfg.get('dhcp_error')

        # Restaurar status preservado (no cambiar automáticamente al guardar config)
        new_cfg['status'] = preserved_status

        # Guardar la configuración completa
        saved = save_json_config(CONFIG_FILE, new_cfg)
        if not saved:
            return False, f"Error guardando configuración WAN en {CONFIG_FILE}"
        return True, "Configuración WAN guardada"
    except Exception as e:
        return False, f"Error guardando configuración WAN: {e}"


# -----------------------------
# Helpers internos
# -----------------------------

def _start_manual(iface: str, cfg: dict) -> Tuple[bool, str]:
    steps = [
        ("limpiar IP", ["/usr/sbin/ip", "a", "flush", "dev", iface]),
        ("asignar IP", ["/usr/sbin/ip", "a", "add", f"{cfg['ip']}/{cfg['mask']}", "dev", iface]),
        ("habilitar interfaz", ["/usr/sbin/ip", "l", "set", iface, "up"]),
        ("configurar ruta por defecto", ["/usr/sbin/ip", "r", "add", "default", "via", cfg["gateway"], "dev", iface]),
    ]

    for label, cmd in steps:
        success, msg = _run_command(cmd)
        if not success:
            _rollback_manual(iface)
            return False, f"Error al {label}: {msg}"

    dns = cfg.get("dns", [])
    if isinstance(dns, str):
        dns = [d.strip() for d in dns.split(",") if d.strip()]

    if dns:
        success, msg = _run_command(["/usr/bin/resolvectl", "revert", iface])
        if not success:
            _rollback_manual(iface)
            return False, f"Error al revertir DNS: {msg}"
        success, msg = _run_command(["/usr/bin/resolvectl", "dns", iface] + dns)
        if not success:
            _rollback_manual(iface)
            return False, f"Error al configurar DNS: {msg}"

    return True, "OK"


def _rollback_manual(iface: str) -> None:
    _run_command(["/usr/bin/resolvectl", "revert", iface])
    _run_command(["/usr/sbin/ip", "r", "flush", "dev", iface])
    _run_command(["/usr/sbin/ip", "a", "flush", "dev", iface])
    _run_command(["/usr/sbin/ip", "link", "set", iface, "down"])


def _validate_manual_network(ip: str, mask: Any, gateway: str) -> Tuple[bool, str]:
    try:
        mask_int = int(mask)
        if mask_int < 0 or mask_int > 32:
            return False, "Mascara invalida. Use un valor entre 0 y 32."

        network = ipaddress.ip_network(f"{ip}/{mask_int}", strict=False)
        ip_addr = ipaddress.ip_address(ip)
        gw_addr = ipaddress.ip_address(gateway)

        if ip_addr in (network.network_address, network.broadcast_address):
            return False, f"IP invalida: {ip} es direccion de red o broadcast para /{mask_int}"

        if gw_addr not in network:
            return False, f"Gateway fuera de red: {gateway} no pertenece a {network}"

        if gw_addr in (network.network_address, network.broadcast_address):
            return False, f"Gateway invalido: {gateway} es direccion de red o broadcast"

        if gw_addr == ip_addr:
            return False, "Gateway invalido: no puede ser igual a la IP"

        return True, ""
    except (ValueError, TypeError):
        return False, "Parametros de red invalidos para IP, mascara o gateway"


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