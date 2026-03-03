import os
import signal
import subprocess
from typing import Dict, Any, Tuple, Optional
from ...utils.global_helpers import (
    load_json_config, save_json_config, update_module_status, run_command
)
from .helpers import generate_dnsmasq_conf, get_dnsmasq_pid

# Caminos
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CONFIG_DIR = os.path.join(BASE_DIR, "config", "dhcp")
CONFIG_FILE = os.path.join(CONFIG_DIR, "dhcp.json")
DNSMASQ_CONF = os.path.join(CONFIG_DIR, "dnsmasq.conf")
PID_FILE = os.path.join(CONFIG_DIR, "dnsmasq.pid")
LOG_FILE = os.path.join(BASE_DIR, "logs", "dhcp", "dnsmasq.log")

DEFAULT_CONFIG = {
    "status": 0,
    "dns_servers": ["8.8.8.8", "8.8.4.4"],
    "lease_time": "12h",
    "vlan_configs": {}
}

def _load_config() -> Dict[str, Any]:
    return load_json_config(CONFIG_FILE, DEFAULT_CONFIG)

def _save_config(cfg: Dict[str, Any]) -> bool:
    return save_json_config(CONFIG_FILE, cfg)

def _update_status(status: int):
    update_module_status(CONFIG_FILE, status)

def start(params: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
    """Inicia el servicio dnsmasq."""
    cfg = _load_config()
    
    # Comprobar si ya está corriendo
    pid = get_dnsmasq_pid()
    if pid:
        return True, f"DHCP ya está en ejecución (PID: {pid})"
    
    # Generar fichero de configuración de dnsmasq
    conf_content, warnings = generate_dnsmasq_conf(cfg)
    if warnings:
        for w in warnings:
            print(f"ADVERTENCIA: {w}")
    try:
        with open(DNSMASQ_CONF, "w") as f:
            f.write(conf_content)
    except Exception as e:
        return False, f"Error al generar dnsmasq.conf: {str(e)}"
    
    # Ejecutar dnsmasq
    # -n: flag non-interactive para sudo
    cmd = [
        "sudo", "-n", "/usr/sbin/dnsmasq", 
        f"--conf-file={DNSMASQ_CONF}",
        f"--pid-file={PID_FILE}",
        f"--log-facility={LOG_FILE}"
    ]
    
    # Usamos run_command con use_sudo=False porque ya ponemos sudo -n
    success, msg = run_command(cmd, use_sudo=False)
    if not success:
        return False, f"Error al iniciar dnsmasq: {msg}"
    
    _update_status(1)
    return True, "Servicio DHCP iniciado correctamente"

def stop(params: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
    """Detiene el servicio dnsmasq."""
    pid = get_dnsmasq_pid()
    if not pid:
        _update_status(0)
        return True, "El servicio DHCP no está en ejecución"
    
    # Matar el proceso
    success, msg = run_command(["sudo", "-n", "kill", str(pid)], use_sudo=False)
    if not success:
        return False, f"Error al detener dnsmasq (PID {pid}): {msg}"
    
    # Limpiamos el fichero PID si el comando falló en borrarlo o para ser proactivos
    if os.path.exists(PID_FILE):
        try:
            os.remove(PID_FILE)
        except:
            pass

    _update_status(0)
    return True, "Servicio DHCP detenido"

def restart(params: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
    """Reinicia el servicio DHCP."""
    ok, msg = stop()
    if not ok:
        return False, msg
    return start()

def status(params: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
    """Devuelve el estado detallado del servicio DHCP."""
    cfg = _load_config()
    pid = get_dnsmasq_pid()
    
    status_msg = "Estado del Módulo DHCP:\n"
    status_msg += "=" * 30 + "\n"
    status_msg += f"Servicio: {'🟢 ACTIVO' if pid else '🔴 INACTIVO'}\n"
    if pid:
        status_msg += f"PID: {pid}\n"
    
    status_msg += f"DNS Upstream: {', '.join(cfg.get('dns_servers', []))}\n"
    status_msg += f"Tiempo de concesión: {cfg.get('lease_time')}\n"
    
    # Mostrar logs (últimas 5 líneas)
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                lines = f.readlines()
                last_logs = "".join(lines[-5:])
                status_msg += "\nÚltimos logs:\n" + last_logs
        except:
            pass
            
    return True, status_msg

def list_leases(params: Optional[Dict[str, Any]] = None) -> Tuple[bool, Any]:
    """Lista las concesiones (leases) activas del servidor DHCP."""
    LEASE_FILE = "/var/lib/misc/dnsmasq.leases"
    if not os.path.exists(LEASE_FILE):
        return True, [] # Retornar lista vacía si no existe el fichero
    
    leases = []
    try:
        with open(LEASE_FILE, "r") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 5:
                    # Formato: timestamp mac ip hostname client-id
                    leases.append({
                        "timestamp": parts[0],
                        "mac": parts[1],
                        "ip": parts[2],
                        "hostname": parts[3] if parts[3] != "*" else "Desconocido",
                        "client_id": parts[4] if parts[4] != "*" else ""
                    })
        return True, leases
    except Exception as e:
        return False, f"Error al leer concesiones DHCP: {str(e)}"

def config(params: Dict[str, Any]) -> Tuple[bool, str]:
    """Configura los parámetros del servidor DHCP."""
    if not params:
        return False, "No se proporcionaron parámetros"
    
    cfg = _load_config()
    changed = False
    
    # Configurar DNS
    if "dns" in params:
        dns_input = params["dns"]
        if isinstance(dns_input, str):
            dns_list = [d.strip() for d in dns_input.split(",") if d.strip()]
        elif isinstance(dns_input, list):
            dns_list = dns_input
        else:
            return False, "Formato de DNS inválido (esperado string o lista)"
        
        cfg["dns_servers"] = dns_list
        changed = True
        
    # Configurar Lease Time
    if "lease_time" in params:
        cfg["lease_time"] = str(params["lease_time"])
        changed = True
        
    # Configurar rangos específicos por VLAN (individual o masivo)
    if "vlan_configs" in params and isinstance(params["vlan_configs"], dict):
        if "vlan_configs" not in cfg:
            cfg["vlan_configs"] = {}
        for vid, vcfg in params["vlan_configs"].items():
            vid_str = str(vid)
            if vid_str not in cfg["vlan_configs"]:
                cfg["vlan_configs"][vid_str] = {}
            if "start" in vcfg: cfg["vlan_configs"][vid_str]["start"] = vcfg["start"]
            if "end" in vcfg: cfg["vlan_configs"][vid_str]["end"] = vcfg["end"]
            if "dns" in vcfg: cfg["vlan_configs"][vid_str]["dns"] = vcfg["dns"]
        changed = True
    elif "vlan_id" in params and ("start" in params or "end" in params):
        vid = str(params["vlan_id"])
        if "vlan_configs" not in cfg:
            cfg["vlan_configs"] = {}
        if vid not in cfg["vlan_configs"]:
            cfg["vlan_configs"][vid] = {}
            
        if "start" in params:
            cfg["vlan_configs"][vid]["start"] = params["start"]
        if "end" in params:
            cfg["vlan_configs"][vid]["end"] = params["end"]
        if "dns" in params:
            cfg["vlan_configs"][vid]["dns"] = params["dns"]
        changed = True

    if changed:
        if _save_config(cfg):
            # Si el servicio está activo, reiniciamos para aplicar cambios
            if get_dnsmasq_pid():
                restart()
            return True, "Configuración DHCP actualizada"
        else:
            return False, "Error al guardar la configuración"
            
    return False, "No se realizaron cambios"

ALLOWED_ACTIONS = {
    "start": start,
    "stop": stop,
    "restart": restart,
    "status": status,
    "config": config,
    "list_leases": list_leases
}
