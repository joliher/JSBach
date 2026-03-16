# app/core/expect/state_manager.py
import os
import json
from datetime import datetime
from typing import Dict, Any, Optional

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
STATE_JSON = os.path.join(BASE_DIR, "config", "expect", "state.json")

def load_state() -> Dict[str, Any]:
    """Carga el estado actual desde state.json."""
    if not os.path.exists(STATE_JSON):
        return {"switches": {}}
    try:
        with open(STATE_JSON, "r") as f:
            return json.load(f)
    except Exception:
        return {"switches": {}}

def save_state(state: Dict[str, Any]) -> bool:
    """Guarda el estado en state.json."""
    try:
        os.makedirs(os.path.dirname(STATE_JSON), exist_ok=True)
        with open(STATE_JSON, "w") as f:
            json.dump(state, f, indent=4)
        return True
    except Exception:
        return False

def get_switch_state(ip: str) -> Dict[str, Any]:
    """Obtiene el estado de un switch específico."""
    state = load_state()
    return state.get("switches", {}).get(ip, {})

def update_mac_block(ip: str, mac: str, rule_id: str, action: str = "block", acl_name: Optional[str] = None):
    """Actualiza el estado de bloqueo de una MAC."""
    state = load_state()
    switches = state.setdefault("switches", {})
    sw_state = switches.setdefault(ip, {})
    mac_acl = sw_state.setdefault("mac_acl", {})
    
    if action == "block":
        mac_acl[mac] = {
            "rule_id": rule_id,
            "acl_name": acl_name,
            "blocked_at": datetime.now().isoformat()
        }
    elif action == "unblock":
        if mac in mac_acl:
            del mac_acl[mac]
    
    save_state(state)

def get_active_acl_id(ip: str, default: str = "100", layer: str = "blacklist") -> str:
    """Obtiene el ID de la ACL activa en el switch para una capa específica."""
    sw_state = get_switch_state(ip)
    key = f"active_{layer}_acl_id"
    return sw_state.get(key, default)

def set_active_acl_id(ip: str, acl_id: str, layer: str = "blacklist"):
    """Guarda el ID de la ACL activa en el switch para una capa específica."""
    state = load_state()
    switches = state.setdefault("switches", {})
    sw_state = switches.setdefault(ip, {})
    key = f"active_{layer}_acl_id"
    sw_state[key] = acl_id
    save_state(state)

def is_layer_enabled(ip: str, layer: str = "blacklist") -> bool:
    """Comprueba si una capa de seguridad está habilitada."""
    sw_state = get_switch_state(ip)
    key = f"{layer}_enabled"
    # Por defecto, blacklist habilitada, whitelist deshabilitada
    default = True if layer == "blacklist" else False
    return sw_state.get(key, default)

def set_layer_enabled(ip: str, layer: str, enabled: bool):
    """Habilita o deshabilita una capa de seguridad."""
    state = load_state()
    switches = state.setdefault("switches", {})
    sw_state = switches.setdefault(ip, {})
    key = f"{layer}_enabled"
    sw_state[key] = enabled
    save_state(state)

def update_whitelist(ip: str, mac: str, action: str = "add"):
    """Actualiza el estado de la whitelist de una MAC."""
    state = load_state()
    switches = state.setdefault("switches", {})
    sw_state = switches.setdefault(ip, {})
    whitelist = sw_state.setdefault("whitelist", [])
    
    if action == "add":
        if mac not in whitelist:
            whitelist.append(mac)
    elif action == "remove":
        if mac in whitelist:
            whitelist.remove(mac)
    
    save_state(state)

def toggle_security_mode(ip: str, mode: str = "blacklist"):
    """Cambia el modo de seguridad (blacklist/whitelist) del switch."""
    state = load_state()
    switches = state.setdefault("switches", {})
    sw_state = switches.setdefault(ip, {})
    sw_state["security_mode"] = mode
    save_state(state)

def get_security_mode(ip: str) -> str:
    """Obtiene el modo de seguridad actual del switch."""
    sw_state = get_switch_state(ip)
    return sw_state.get("security_mode", "blacklist")

def clear_switch_state(ip: str):
    """Limpia el estado de un switch (usado en reset)."""
    state = load_state()
    if ip in state.get("switches", {}):
        state["switches"][ip] = {}
        save_state(state)
