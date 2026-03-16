# app/modules/expect/actions/config.py
from typing import Dict, Any, Tuple, Optional
from ..base import async_run_expect_script
from .. import state_manager
from ..helpers import parse_config_blocks

async def run_config(ip: str, actions_raw: str, profile: Dict[str, Any], _auth_required: bool, user: str, password: str, dry_run: bool = False, protocol: Optional[str] = None) -> Tuple[bool, str]:
    from ..base import get_script_path
    commands = []
    
    blocks = parse_config_blocks(actions_raw)
    config_prompt = profile["prompts"]["config"]
    
    for block in blocks:
        ports = block.get("ports")
        params_dict = block.get("params", {})

        if ports:
            port_prefix = profile.get("port_prefix", "ethernet ")
            port_list = [p.strip() for p in str(ports).split(',') if p.strip()]
            for p in port_list:
                commands.append(f"interface {port_prefix}{p}")
                
                for key, val in params_dict.items():
                    cmd_template = profile.get("parameters", {}).get(key, {}).get("cmd")
                    if cmd_template:
                        cmd = cmd_template.replace("{value}", str(val))
                        commands.append(cmd)
                
                commands.append("exit")
        else:
            for key, val in params_dict.items():
                cmd_template = profile.get("parameters", {}).get(key, {}).get("cmd")
                if cmd_template:
                    cmd = cmd_template.replace("{value}", str(val))
                    commands.append(cmd)

    # Configuración vía variable de entorno (Zero-Disk)
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
        
        script_path = get_script_path("generic_config")
        if dry_run:
            with open(script_path, 'r') as f:
                return True, f"MODO SIMULACIÓN (Script Externo):\n{f.read()}\n\nCOMANDOS:\n" + "\n".join(commands)
            
        success, stdout, stderr = await async_run_expect_script(script_path, timeout=180, env_vars=env_vars)
        if success:
            state = state_manager.load_state()
            state.setdefault("switches", {}).setdefault(ip, {})["last_config"] = {
                "timestamp": state_manager.datetime.now().isoformat(),
                "status": "success"
            }
            state_manager.save_state(state)
        return success, stdout if success else f"Error en configuración: {stderr or stdout}"
    except Exception as e:
        return False, f"Error ejecutando configuración: {e}"

async def run_reset(ip: str, profile: Dict[str, Any], _auth_required: bool, user: str, password: str, max_ports: int, dry_run: bool = False, protocol: Optional[str] = None) -> Tuple[bool, str]:
    from ..base import get_script_path
    commands = []
    
    reset_cmd_tmpl = profile.get("reset_cmd")
    if not reset_cmd_tmpl:
        return False, "El perfil no soporta la función de reset."

    config_prompt = profile["prompts"]["config"]
    port_prefix = profile.get("port_prefix", "ethernet ")
    cmds = [c.strip() for c in reset_cmd_tmpl.split(',')]
    
    if profile.get("range_support"):
        range_str = f"{port_prefix}1-{max_ports}"
        commands.append(f"interface range {range_str}")
        for cmd in cmds:
            actual_cmd = cmd.replace("{port}", range_str)
            commands.append(actual_cmd)
        commands.append("exit")
    else:
        for i in range(1, max_ports + 1):
            commands.append(f"interface {port_prefix}{i}")
            for cmd in cmds:
                actual_cmd = cmd.replace("{port}", str(i))
                commands.append(actual_cmd)
            commands.append("exit")

    # Reset vía variable de entorno (Zero-Disk)
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
        
        script_path = get_script_path("generic_config")
        if dry_run:
            with open(script_path, 'r') as f:
                return True, f"MODO SIMULACIÓN (Reset - Script Externo):\n{f.read()}\n\nCOMANDOS:\n" + "\n".join(commands)
            
        success, stdout, stderr = await async_run_expect_script(script_path, timeout=180, env_vars=env_vars)
        if success:
            state_manager.clear_switch_state(ip)
        return success, stdout if success else f"Error en reset: {stderr or stdout}"
    except Exception as e:
        return False, f"Error ejecutando reset: {e}"
