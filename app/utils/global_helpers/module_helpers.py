import os
import json
import logging
import subprocess
import re
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

# --- Funciones de carga de JSON ---

def load_json_config(file_path: str, default_value: Any = None) -> Any:
    if not os.path.exists(file_path):
        return default_value
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f'Error cargando configuración de {file_path}: {str(e)}')
        return default_value

def save_json_config(file_path: str, data: Any) -> bool:
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4)
        return True
    except Exception as e:
        logger.error(f'Error guardando configuración en {file_path}: {str(e)}')
        return False

# --- Validación y Utilería de Red ---

def validate_interface_name(iface: str) -> bool:
    if not iface or not isinstance(iface, str): return False
    return bool(re.match(r'^[a-zA-Z0-9._-]+$', iface)) and len(iface) < 16

def sanitize_interface_name(iface: str) -> str:
    if not iface: return ''
    return re.sub(r'[^a-zA-Z0-9._-]', '', str(iface))[:15]

def interface_exists(iface: str) -> bool:
    if not iface: return False
    return os.path.exists(f'/sys/class/net/{sanitize_interface_name(iface)}')

def get_wan_interface(base_dir: str) -> str:
    cfg = load_module_config(base_dir, 'wan', {})
    return cfg.get('interface', '')

# --- Helpers de Módulos ---

def get_config_file_path(base_dir: str, module_name: str) -> str:
    return os.path.join(base_dir, 'config', module_name, f'{module_name}.json')

def get_log_file_path(base_dir: str, module_name: str) -> str:
    return os.path.join(base_dir, 'logs', module_name, f'{module_name}.log')

def load_module_config(base_dir: str, module_name: str, default_value: Any = None) -> Any:
    path = get_config_file_path(base_dir, module_name)
    return load_json_config(path, default_value)

def ensure_module_dirs(base_dir: str, module_name: str):
    os.makedirs(os.path.join(base_dir, 'config', module_name), exist_ok=True)
    os.makedirs(os.path.join(base_dir, 'logs', module_name), exist_ok=True)

# --- Gestión de Estado ---

def get_module_status(file_path: str) -> int:
    try:
        cfg = load_json_config(file_path, {})
        return cfg.get('status', 0)
    except:
        return 0

def get_module_status_by_name(base_dir: str, module_name: str) -> int:
    path = get_config_file_path(base_dir, module_name)
    return get_module_status(path)

def update_module_status(file_path: str, status: int) -> bool:
    cfg = load_json_config(file_path, {})
    cfg['status'] = status
    return save_json_config(file_path, cfg)

# --- Dependencias ---

def check_module_dependencies(base_dir: str, module_name: str = None) -> Tuple[bool, str]:
    if module_name is None: return True, 'Dependencias satisfechas'
    if module_name in ['wan', 'wifi', 'vlans']: return True, 'Dependencias satisfechas'
    if module_name == 'tagging':
        if get_module_status_by_name(base_dir, 'vlans') != 1:
            return False, 'Error: El módulo VLANs debe estar activo.'
        return True, 'Dependencias satisfechas'
    wan_cfg = load_module_config(base_dir, 'wan', {})
    if not wan_cfg.get('interface'): return False, 'Error: El módulo WAN debe estar configurado.'
    if module_name in ['nat', 'dhcp']: return True, 'Dependencias satisfechas'
    if get_module_status_by_name(base_dir, 'vlans') != 1:
        if module_name == 'firewall' and get_module_status_by_name(base_dir, 'wifi') == 1: pass
        else: return False, 'Error: El módulo VLANs debe estar activo.'
    if get_module_status_by_name(base_dir, 'tagging') != 1:
        if module_name == 'firewall' and get_module_status_by_name(base_dir, 'wifi') == 1: pass
        else: return False, 'Error: El módulo Tagging debe estar activo.'
    return True, 'Dependencias satisfechas'

# --- Firewall & Ebtables Helpers ---

def ensure_global_chains():
    for table in ['filter', 'nat']:
        chains = ['JSB_GLOBAL_STATS', 'JSB_GLOBAL_ISOLATE'] if table == 'filter' else ['JSB_POSTROUTING']
        for chain in chains:
            run_command(['/usr/sbin/iptables', '-t', table, '-N', chain], ignore_error=True)
            parent = 'FORWARD' if table == 'filter' else 'POSTROUTING'
            success, _ = run_command(['/usr/sbin/iptables', '-t', table, '-C', parent, '-j', chain], ignore_error=True)
            if not success:
                run_command(['/usr/sbin/iptables', '-t', table, '-I', parent, '1', '-j', chain], ignore_error=True)

def ensure_ebtables_global_chains():
    """Asegura cadenas globales en ebtables."""
    for chain in ['JSB_GLOBAL_EBT_STATS', 'JSB_GLOBAL_EBT_ISOLATE']:
        run_command(['/usr/sbin/ebtables', '-t', 'filter', '-N', chain], ignore_error=True)
        # ebtables (nf_tables) NO soporta -C para comprobar reglas de forma confiable
        # Patrón seguro: Borrar e Insertar
        run_command(['/usr/sbin/ebtables', '-t', 'filter', '-D', 'FORWARD', '-j', chain], ignore_error=True)
        run_command(['/usr/sbin/ebtables', '-t', 'filter', '-I', 'FORWARD', '1', '-j', chain], ignore_error=True)

def ensure_module_hook(table: str, parent_chain: str, module_chain: str, pos: int = 1, binary: str = '/usr/sbin/iptables'):
    """Inserta un hook de iptables o ebtables dinámicamente."""
    if binary == 'ebtables': binary = '/usr/sbin/ebtables'
    elif binary == 'iptables': binary = '/usr/sbin/iptables'
    
    cmd_base = [binary, '-t', table]
    run_command(cmd_base + ['-N', module_chain], ignore_error=True)
    
    if 'ebtables' in binary:
        run_command(cmd_base + ['-D', parent_chain, '-j', module_chain], ignore_error=True)
        run_command(cmd_base + ['-I', parent_chain, str(pos), '-j', module_chain], ignore_error=True)
    else:
        success, _ = run_command(cmd_base + ['-C', parent_chain, '-j', module_chain], ignore_error=True)
        if not success:
            run_command(cmd_base + ['-I', parent_chain, str(pos), '-j', module_chain], ignore_error=True)

# --- Ejecución de Comandos ---

def run_command(cmd: list, use_sudo: bool = True, timeout: int = 30, ignore_error: bool = False) -> Tuple[bool, str]:
    try:
        full_cmd = ['sudo', '-n'] + cmd if use_sudo else cmd
        result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            return True, result.stdout.strip()
        else:
            msg = result.stderr.strip() or result.stdout.strip()
            if not ignore_error:
                logger.error(f'Comando fallido: {" ".join(full_cmd)} - Error: {msg}')
            return False, msg
    except Exception as e:
        if not ignore_error:
            logger.error(f'Error ejecutando comando {cmd}: {str(e)}')
        return False, str(e)
