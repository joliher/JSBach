# app/modules/expect/actions/mac.py
import re
from typing import Dict, Any, Tuple, cast, Optional
from ..base import (
    async_run_expect_script, get_script_path
)
from .. import state_manager
from ..helpers import normalize_mac


def mac_rule_id(mac: str, base: int = 1, span: int = 511) -> str:
    compact = re.sub(r"[^0-9A-Fa-f]", "", mac or "")
    if len(compact) < 4:
        return str(base)
    value = int(compact[-4:], 16)
    return str(base + (value % span))

def mac_acl_name(profile: Dict[str, Any], mac: str) -> str:
    compact = re.sub(r"[^0-9A-Fa-f]", "", mac or "").lower()
    safe_compact = re.sub(r"[^a-zA-Z0-9_-]", "_", compact)
    # Generar un ID numérico (ej. 1-99 para ACLs MAC en TP-Link)
    try:
        numeric_id = str(1 + (int(compact[-4:], 16) % 95)) # Evitar 99 por si acaso hay límites
    except:
        numeric_id = "1"
    
    template = profile.get("mac_acl_name_template", "mac_blocked_{mac_compact}")
    name = template.format(mac=mac, mac_compact=safe_compact, mac_id=numeric_id)
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name)

async def run_mac_table(ip: str, profile: Dict[str, Any], auth_required: bool, user: str, password: str, protocol: Optional[str] = None) -> Tuple[bool, str]:
    from ..base import get_script_path
    
    env_vars = {
        "PROTOCOL": protocol or profile.get("auth_type", "telnet"),
        "IP": ip,
        "USER": user,
        "LOGIN_PROMPT": profile["prompts"]["login"],
        "PASSWORD_PROMPT": profile["prompts"]["password"],
        "EXEC_PROMPT": profile["prompts"]["exec"],
        "PRIV_PROMPT": profile["prompts"]["exec_priv"],
        "MAC_TABLE_CMD": profile.get("mac_table_cmd", "show mac address-table"),
        "EXPECT_PASS": password or ""
    }
    
    try:
        script_path = get_script_path("mac_table")
        success, stdout, stderr = await async_run_expect_script(script_path, timeout=30, env_vars=env_vars)
        
        if not success and ("MAC" in stdout and "VLAN" in stdout):
            success = True
            
        return success, stdout if success else f"Error consultando tabla MAC: {stderr or stdout}"
    except Exception as e:
        return False, f"Error ejecutando mac_table: {e}"

async def run_mac_acl_isolate(ip: str, mac: str, profile: Dict[str, Any], auth_required: bool, user: str, password: str, max_ports: int, protocol: Optional[str] = None) -> Tuple[bool, str]:
    # 1. Update local state ONLY
    mac_norm = normalize_mac(mac)
    state_manager.update_mac_block(ip, mac_norm, "0", "block", acl_name="JSBACH_SECURITY")
    return True, f"MAC {mac} marcada para AISLAR. Pulse SINCRONIZAR para aplicar."

async def run_mac_acl_unisolate(ip: str, mac: str, profile: Dict[str, Any], auth_required: bool, user: str, password: str, max_ports: int, protocol: Optional[str] = None) -> Tuple[bool, str]:
    # 1. Update local state ONLY
    mac_norm = normalize_mac(mac)
    state_manager.update_mac_block(ip, mac_norm, "", "unblock")
    return True, f"MAC {mac} marcada para DESAISLAR. Pulse SINCRONIZAR para aplicar."
