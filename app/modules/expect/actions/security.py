# app/modules/expect/actions/security.py
from typing import Dict, Any, Tuple, Optional
from ..base import async_run_expect_script
from .. import state_manager
from ..helpers import normalize_mac

async def run_sync_security(ip: str, profile: Dict[str, Any], _auth_required: bool, user: str, password: str, max_ports: int, protocol: Optional[str] = None) -> Tuple[bool, str]:
    from ..base import get_script_path
    
    sec_cmds = profile.get("mac_security_cmds")
    if not sec_cmds or "layers" not in sec_cmds:
        return False, "El perfil no soporta la arquitectura de capas de seguridad."

    sw_state = state_manager.get_switch_state(ip)
    layers_cfg = sec_cmds.get("layers", [])
    config_prompt = profile["prompts"]["config"]
    
    commands = []
    sync_results = {}

    # --- PART 1: PREPARE SHADOW ACLs ---
    for layer in layers_cfg:
        lid = layer["id"]
        enabled = state_manager.is_layer_enabled(ip, lid)
        p_id = layer["primary_id"]
        s_id = layer["shadow_id"]
        current = state_manager.get_active_acl_id(ip, p_id, lid)
        shadow = s_id if current == p_id else p_id
        
        sync_results[lid] = {"enabled": enabled, "current": current, "shadow": shadow, "config": layer}

        if enabled:
            # Clean Shadow
            commands.append(sec_cmds['remove_acl'].format(acl_id=shadow))
            
            # Create Shadow
            commands.append(layer['create_cmd'].format(acl_id=shadow))

            mac_fmt = profile.get("mac_format", "colons")
            def _fmt_mac(m):
                norm = normalize_mac(m)
                return norm.replace(":", "-") if mac_fmt == "dashed" else norm

            policy = layer.get("rule_policy")
            if policy == "deny_isolated":
                data = sw_state.get("mac_acl", {})
                for idx, (mac, _) in enumerate(data.items()):
                    if idx >= 999: break
                    cmd = sec_cmds["deny_mac"].format(acl_id=shadow, rule_id=idx+1, mac=_fmt_mac(mac))
                    commands.append(cmd)
            
            elif policy == "permit_whitelisted":
                data = sw_state.get("whitelist", [])
                for idx, mac in enumerate(data):
                    if idx >= 999: break
                    cmd = sec_cmds["permit_mac"].format(acl_id=shadow, rule_id=idx+1, mac=_fmt_mac(mac))
                    commands.append(cmd)

            if layer.get("adaptive_final"):
                wl_data = sw_state.get("whitelist", [])
                adaptive = sec_cmds["deny_any"] if len(wl_data) > 0 else sec_cmds["permit_any"]
                commands.append(adaptive.format(acl_id=shadow))
            else:
                final_key = layer.get("final_rule", "permit_any")
                commands.append(sec_cmds[final_key].format(acl_id=shadow))

    # --- PART 2: ATOMIC SWAP ---
    port_prefix = profile.get("port_prefix", "")
    
    for lid, res in sync_results.items():
        layer = res["config"]
        target_type = layer.get("target")
        
        if target_type == "ports":
            target = f"{port_prefix}1-{max_ports}"
        elif target_type == "ports_excl_p1":
            target = f"{port_prefix}2-{max_ports}"
        else:
            target = layer.get("target", "1")
        
        # Unbind OLD
        cmd_unbind = layer["remove_apply_cmd"].format(acl_id=res["current"], target=target, interface=target, vlan_id=target)
        commands.append(cmd_unbind)

        if res["enabled"]:
            # Bind NEW
            cmd_bind = layer["apply_cmd"].format(acl_id=res["shadow"], target=target, interface=target, vlan_id=target)
            commands.append(cmd_bind)

    # --- PART 3: CLEANUP ---
    for lid, res in sync_results.items():
        if res["enabled"]:
            commands.append(sec_cmds['remove_acl'].format(acl_id=res['current']))
        else:
            p_id, s_id = res["config"]["primary_id"], res["config"]["shadow_id"]
            for aid in [p_id, s_id]:
                commands.append(sec_cmds['remove_acl'].format(acl_id=aid))

        # LOG DE ESCENARIOS (Depuración de Comandos Reales)
        # Eliminado para cumplir con Zero-Disk. Si se requiere depuración, usar logs de sistema.
        pass

    try:
        env_vars = {
            "PROTOCOL": protocol or profile.get("auth_type", "telnet"),
            "IP": ip,
            "USER": user,
            "LOGIN_PROMPT": profile["prompts"]["login"],
            "PASSWORD_PROMPT": profile["prompts"]["password"],
            "EXEC_PROMPT": profile["prompts"]["exec"],
            "PRIV_PROMPT": profile["prompts"]["exec_priv"],
            "CONFIG_PROMPT": config_prompt,
            "CLI_COMMANDS": "\n".join(commands),
            "SAVE_CMD": profile.get("save_cmd", "write memory"),
            "EXPECT_PASS": password or ""
        }
        
        script_path = get_script_path("security_sync")
        success, stdout, stderr = await async_run_expect_script(script_path, timeout=180, env_vars=env_vars)
        
        if success:
            for lid, res in sync_results.items():
                if res["enabled"]:
                    state_manager.set_active_acl_id(ip, res["shadow"], lid)
            
        return success, stdout if success else f"Error sincronizando seguridad: {stderr or stdout}"
    except Exception as e:
        return False, f"Error ejecutando sincronización de seguridad: {e}"
    finally:
        pass
