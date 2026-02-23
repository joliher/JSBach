# app/modules/expect/__init__.py
import os
import json
from typing import Dict, Any, Tuple, Optional, cast
from . import state_manager, actions
from .base import logger
from app.utils.global_helpers import (
    load_json_config, save_json_config, update_module_status,
    run_command, ensure_module_dirs, get_module_logger
)
from .helpers import (
    check_ip_reachability, validate_port_range, parse_config_blocks,
    validate_vlan_string, sanitize_config_value, load_profile,
    get_secrets
)
from ...utils.validators import validate_ip_address
from app.utils import crypto_helper, sanitization_helper

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CONFIG_DIR = os.path.join(BASE_DIR, "config", "expect")
SWITCHES_JSON = os.path.join(CONFIG_DIR, "switches.json")
SECRETS_JSON = os.path.join(CONFIG_DIR, "secrets.json")
PROFILES_DIR = os.path.join(CONFIG_DIR, "profiles")

def _load_switch(ip: str) -> Optional[Dict[str, Any]]:
    cfg = load_json_config(SWITCHES_JSON)
    return next((s for s in cfg.get("switches", []) if s.get("ip") == ip), None)

# Actions
async def mac_table(params: Dict[str, Any]) -> Tuple[bool, str]:
    ip = sanitization_helper.sanitize_ip_or_host(params.get("ip"))
    
    sw = _load_switch(ip)
    if not sw: return False, f"Switch {ip} no encontrado"
    profile = load_profile(sw["profile"], PROFILES_DIR)
    user, password = get_secrets(ip, SECRETS_JSON)
    protocol = sw.get("protocol")
    
    # Los secretos se pasan via env, deben ser literales
    
    return await actions.mac.run_mac_table(ip, profile, True, user, password, protocol=protocol)

async def isolate(params: Dict[str, Any]) -> Tuple[bool, str]:
    ip = sanitization_helper.sanitize_ip_or_host(params.get("ip"))
    mac = sanitization_helper.sanitize_cli_command(params.get("mac"))
    
    sw = _load_switch(ip)
    if not sw: return False, f"Switch {ip} no encontrado"
    profile = load_profile(sw["profile"], PROFILES_DIR)
    max_ports = sw.get("max_ports") or profile.get("max_ports", 24)
    user, password = get_secrets(ip, SECRETS_JSON)
    protocol = sw.get("protocol")
    
    # Los secretos se pasan via env, deben ser literales
    
    return await actions.mac.run_mac_acl_isolate(ip, mac, profile, True, user, password, max_ports, protocol=protocol)

async def unisolate(params: Dict[str, Any]) -> Tuple[bool, str]:
    ip = sanitization_helper.sanitize_ip_or_host(params.get("ip"))
    mac = sanitization_helper.sanitize_cli_command(params.get("mac"))
    
    sw = _load_switch(ip)
    if not sw: return False, f"Switch {ip} no encontrado"
    profile = load_profile(sw["profile"], PROFILES_DIR)
    max_ports = sw.get("max_ports") or profile.get("max_ports", 24)
    user, password = get_secrets(ip, SECRETS_JSON)
    protocol = sw.get("protocol")
    
    # Los secretos se pasan via env, deben ser literales
    
    return await actions.mac.run_mac_acl_unisolate(ip, mac, profile, True, user, password, max_ports, protocol=protocol)

async def config(params: Dict[str, Any]) -> Tuple[bool, str]:
    ip = sanitization_helper.sanitize_ip_or_host(params.get("ip"))
    actions_raw = sanitization_helper.sanitize_cli_command(params.get("actions"))
    dry_run = params.get("dry_run", False)
    
    sw = _load_switch(ip)
    if not sw: return False, f"Switch {ip} no encontrado"
    profile = load_profile(sw["profile"], PROFILES_DIR)
    user, password = get_secrets(ip, SECRETS_JSON)
    protocol = sw.get("protocol")
    
    # Los secretos se pasan via env, deben ser literales
    
    return await actions.config.run_config(ip, actions_raw, profile, True, user, password, dry_run, protocol=protocol)

async def reset(params: Dict[str, Any]) -> Tuple[bool, str]:
    ip = sanitization_helper.sanitize_ip_or_host(params.get("ip"))
    
    sw = _load_switch(ip)
    if not sw: return False, f"Switch {ip} no encontrado"
    profile = load_profile(sw["profile"], PROFILES_DIR)
    max_ports = sw.get("max_ports") or profile.get("max_ports", 24)
    user, password = get_secrets(ip, SECRETS_JSON)
    protocol = sw.get("protocol")
    
    user = sanitization_helper.sanitize_expect_input(user)
    password = sanitization_helper.sanitize_expect_input(password)
    
    return await actions.config.run_reset(ip, profile, True, user, password, max_ports, protocol=protocol)

def get_state(params: Dict[str, Any]) -> Tuple[bool, str]:
    ip = params.get("ip")
    if ip:
        sw = _load_switch(ip)
        if not sw: return False, "Switch no encontrado"
        profile = load_profile(sw["profile"], PROFILES_DIR)
        sec_cmds = profile.get("mac_security_cmds", {})
        layers = sec_cmds.get("layers", [])
        
        sw_state = state_manager.get_switch_state(ip)
        
        # Prepare dynamic layer info for frontend
        layers_info = []
        for l in layers:
            lid = l["id"]
            layers_info.append({"id": lid, "name": l["name"]})
            # Ensure each layer has a default enabled state in sw_state if not present
            if f"{lid}_enabled" not in sw_state:
                sw_state[f"{lid}_enabled"] = (lid == "blacklist") # Default: bl=True, wl=False
                
        sw_state["layers_info"] = layers_info
        return True, json.dumps(sw_state)
    return True, json.dumps(state_manager.load_state())

# Maintenance Actions (Passthrough to old expect.py if needed, or implement here)
def auth(params: Dict[str, Any]) -> Tuple[bool, str]:
    ip = params.get("ip")
    user = params.get("user")
    password = params.get("password", "")
    if not ip or not user: return False, "Faltan parámetros: ip, user"
    secrets = load_json_config(SECRETS_JSON)
    secrets[ip] = {"user": user, "password": password or ""}
    save_json_config(SECRETS_JSON, secrets)
    return True, f"Credenciales guardadas para {ip}"

def list_switches(params: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
    cfg = load_json_config(SWITCHES_JSON)
    secrets = load_json_config(SECRETS_JSON)
    result = []
    for sw in cfg.get("switches", []):
        ip = sw.get("ip")
        creds = secrets.get(ip, {})
        result.append({**sw, "user": creds.get("user", ""), "password": creds.get("password", "")})
    return True, json.dumps({"switches": result})

def _update_credentials(ip: str, user: str, password: Optional[str] = None):
    secrets = load_json_config(SECRETS_JSON)
    if ip not in secrets:
        secrets[ip] = {"user": user, "password": ""}
    
    secrets[ip]["user"] = user
    if password is not None:
        # Cifrar password si existe una llave maestra
        encrypted_password = password
        try:
            key = crypto_helper.get_master_key()
            if key:
                encrypted_password = crypto_helper.encrypt_string(password, key)
        except Exception as e:
            # logs is not imported as a logger object here, but get_module_logger is available
            pass
            
        secrets[ip]["password"] = encrypted_password
        
    save_json_config(SECRETS_JSON, secrets)

def add_switch(params: Dict[str, Any]) -> Tuple[bool, str]:
    ip = params.get("ip")
    cfg = load_json_config(SWITCHES_JSON)
    switches = cfg.setdefault("switches", [])
    
    # Busca si existe para actualizar o añadir
    existing = next((s for s in switches if s.get("ip") == ip), None)
    new_data = {
        "name": params["name"],
        "ip": ip,
        "profile": params["profile"],
        "max_ports": params.get("max_ports", 24),
        "protocol": params.get("protocol", "telnet")
    }
    
    if existing:
        existing.update(new_data)
    else:
        switches.append(new_data)
        
    save_json_config(SWITCHES_JSON, cfg)
    
    # Actualizar credenciales si vienen en el request
    password = params.get("password")
    _update_credentials(ip, params["user"], password)
    
    return True, "Switch guardado"

def update_switch(params: Dict[str, Any]) -> Tuple[bool, str]:
    return add_switch(params)

def remove_switch(params: Dict[str, Any]) -> Tuple[bool, str]:
    ip = params.get("ip")
    cfg = load_json_config(SWITCHES_JSON)
    cfg["switches"] = [s for s in cfg.get("switches", []) if s.get("ip") != ip]
    save_json_config(SWITCHES_JSON, cfg)
    
    # Limpiar secrets asociado
    secrets = load_json_config(SECRETS_JSON)
    if ip in secrets:
        del secrets[ip]
        save_json_config(SECRETS_JSON, secrets)
    return True, "Switch eliminado"

def update_switch(params: Dict[str, Any]) -> Tuple[bool, str]:
    original_ip = params.get("original_ip")
    ip = params.get("ip")
    if not original_ip or not ip: return False, "Faltan IPs"
    
    cfg = load_json_config(SWITCHES_JSON)
    found_sw = None
    for sw in cfg.get("switches", []):
        if sw.get("ip") == original_ip:
            sw["name"] = params.get("name", sw["name"])
            sw["ip"] = ip
            sw["profile"] = params.get("profile", sw["profile"])
            sw["max_ports"] = params.get("max_ports", sw.get("max_ports", 24))
            sw["protocol"] = params.get("protocol", sw.get("protocol", "telnet"))
            found_sw = sw
            break
            
    if not found_sw:
        return False, f"Switch con IP {original_ip} no encontrado"
        
    save_json_config(SWITCHES_JSON, cfg)
    
    # Manejar secrets (actualizar o mover si IP cambió)
    secrets = load_json_config(SECRETS_JSON)
    if original_ip in secrets:
        creds = secrets.pop(original_ip)
        creds["user"] = params.get("user", creds["user"])
        if "password" in params:
            creds["password"] = params["password"]
        secrets[ip] = creds
    else:
        secrets[ip] = {
            "user": params.get("user", "admin"),
            "password": params.get("password", "")
        }
    save_json_config(SECRETS_JSON, secrets)
    
    return True, f"Switch {ip} actualizado"

async def apply_whitelist(params: Dict[str, Any]) -> Tuple[bool, str]:
    ip = sanitization_helper.sanitize_ip_or_host(params.get("ip"))
    
    sw = _load_switch(ip)
    if not sw: return False, f"Switch {ip} no encontrado"
    profile = load_profile(sw["profile"], PROFILES_DIR)
    max_ports = sw.get("max_ports") or profile.get("max_ports", 24)
    user, password = get_secrets(ip, SECRETS_JSON)
    protocol = sw.get("protocol")
    
    user = sanitization_helper.sanitize_expect_input(user)
    password = sanitization_helper.sanitize_expect_input(password)
    
    from .actions.security import run_sync_security
    return await run_sync_security(ip, profile, True, user, password, max_ports, protocol=protocol)

def add_to_whitelist(params: Dict[str, Any]) -> Tuple[bool, str]:
    ip = params.get("ip")
    mac = params.get("mac")
    if not ip or not mac: return False, "Faltan parámetros: ip, mac"
    state_manager.update_whitelist(ip, mac, "add")
    return True, f"MAC {mac} añadida a la Whitelist local. Pulse SINCRONIZAR para aplicar."

def remove_from_whitelist(params: Dict[str, Any]) -> Tuple[bool, str]:
    ip = params.get("ip")
    mac = params.get("mac")
    if not ip or not mac: return False, "Faltan parámetros: ip, mac"
    state_manager.update_whitelist(ip, mac, "remove")
    return True, f"MAC {mac} eliminada de la Whitelist local. Pulse SINCRONIZAR para aplicar."

async def get_whitelist_action(params: Dict[str, Any]) -> Tuple[bool, str]:
    ip = params.get("ip")
    if not ip: return False, "Falta IP"
    
    sw = _load_switch(ip)
    if not sw: return False, "Switch no encontrado"
    profile = load_profile(sw["profile"], PROFILES_DIR)
    sec_cmds = profile.get("mac_security_cmds", {})
    layers = sec_cmds.get("layers", [])
    
    sw_state = state_manager.get_switch_state(ip)
    
    resp = {
        "whitelist": sw_state.get("whitelist", []),
        "layers_info": [{"id": l["id"], "name": l["name"]} for l in layers]
    }
    # Add status for each layer
    for l in layers:
        lid = l["id"]
        resp[f"{lid}_enabled"] = state_manager.is_layer_enabled(ip, lid)
        
    return True, json.dumps(resp)

def status(params: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]: return True, "Módulo Expect Modular activo"
def start(params: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]: return True, "Iniciado"
def stop(params: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]: return True, "Detenido"
def restart(params: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]: return True, "Reiniciado"

async def set_security_toggle(params: Dict[str, Any]) -> Tuple[bool, str]:
    ip = params.get("ip")
    layer = params.get("layer") # 'blacklist' o 'whitelist'
    enabled = params.get("enabled", False)
    if not ip or not layer: return False, "Faltan parámetros: ip, layer"
    
    state_manager.set_layer_enabled(ip, layer, enabled)
    
    # Sync with switch
    sw_result = list_switches()
    sw_data = json.loads(sw_result[1])
    sw_info = next((s for s in sw_data["switches"] if s["ip"] == ip), None)
    if not sw_info: return False, "Switch no encontrado"
        
    profile = load_profile(sw_info["profile"], PROFILES_DIR)
    user, password = get_secrets(ip, SECRETS_JSON)
    
    from .actions.security import run_sync_security
    return await run_sync_security(
        ip, profile, True, user, password, 
        sw_info.get("max_ports", 24), protocol=sw_info.get("protocol")
    )

ALLOWED_ACTIONS = {
    "config": config,
    "auth": auth,
    "list_switches": list_switches,
    "add_switch": add_switch,
    "update_switch": update_switch,
    "remove_switch": remove_switch,
    "mac_table": mac_table,
    "isolate": isolate,
    "unisolate": unisolate,
    "get_state": get_state,
    "add_to_whitelist": add_to_whitelist,
    "remove_from_whitelist": remove_from_whitelist,
    "apply_whitelist": apply_whitelist,
    "get_whitelist": get_whitelist_action,
    "security_toggle": set_security_toggle,
    "reset": reset,
    "status": status,
    "start": start,
    "stop": stop,
    "restart": restart
}
