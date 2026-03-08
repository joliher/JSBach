import os
import time
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
        _update_status(1)
        return True, f"DHCP ya está en ejecución (PID: {pid})"
    
    # Generar fichero de configuración de dnsmasq
    conf_content, warnings = generate_dnsmasq_conf(cfg)
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(DNSMASQ_CONF, "w") as f:
            f.write(conf_content)
    except Exception as e:
        return False, f"Error al generar dnsmasq.conf: {str(e)}"
    
    # Ejecutar dnsmasq
    cmd = [
        "sudo", "-n", "/usr/sbin/dnsmasq", 
        f"--conf-file={DNSMASQ_CONF}",
        f"--pid-file={PID_FILE}",
        f"--log-facility={LOG_FILE}"
    ]
    
    success, msg = run_command(cmd, use_sudo=False)
    if not success:
        return False, f"Error al iniciar dnsmasq: {msg}"
    
    # Esperar un momento a que el PID file aparezca y el proceso se estabilice
    for _ in range(5):
        time.sleep(0.5)
        if get_dnsmasq_pid():
            break

    _update_status(1)
    return True, "Servicio DHCP iniciado correctamente"

def stop(params: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
    """Detiene el servicio dnsmasq."""
    pid = get_dnsmasq_pid()
    if not pid:
        _update_status(0)
        # Limpieza proactiva de conf residual si existe
        if os.path.exists(DNSMASQ_CONF):
            try: os.remove(DNSMASQ_CONF)
            except: pass
        return True, "El servicio DHCP no está en ejecución"
    
    # Matar el proceso
    run_command(["sudo", "-n", "kill", str(pid)], use_sudo=False)
    
    # Esperar a que muera
    timeout = 5
    start_time = time.time()
    while time.time() - start_time < timeout:
        if not get_dnsmasq_pid():
            break
        time.sleep(0.5)
    
    # Si persiste, forzar kill -9
    pid_ext = get_dnsmasq_pid()
    if pid_ext:
        run_command(["sudo", "-n", "kill", "-9", str(pid_ext)], use_sudo=False)

    # Limpieza de ficheros temporales (Zero-Disk en stop)
    for f in [PID_FILE, DNSMASQ_CONF]:
        if os.path.exists(f):
            try: os.remove(f)
            except: pass

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
    
    # Contar leases activas
    ok_leases, leases = list_leases()
    lease_count = len(leases) if ok_leases else 0
    
    status_msg = "Estado del Módulo DHCP:\n"
    status_msg += "=" * 30 + "\n"
    status_msg += f"Servicio: {'🟢 ACTIVO' if pid else '🔴 INACTIVO'}\n"
    if pid:
        status_msg += f"PID: {pid}\n"
    
    status_msg += f"DNS Upstream: {', '.join(cfg.get('dns_servers', []))}\n"
    status_msg += f"Tiempo de concesión: {cfg.get('lease_time')}\n"
    status_msg += f"Leases activas: {lease_count}\n"
    
    # Agrupar leases por red/hostname si hay muchas (opcional, de momento simple)
    
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
        return True, [] 
    
    leases = []
    try:
        with open(LEASE_FILE, "r") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 5:
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
    
    if "dns" in params:
        dns_input = params["dns"]
        dns_list = [d.strip() for d in dns_input.split(",") if d.strip()] if isinstance(dns_input, str) else dns_input
        cfg["dns_servers"] = dns_list
        changed = True
        
    if "lease_time" in params:
        cfg["lease_time"] = str(params["lease_time"])
        changed = True
        
    if "vlan_configs" in params and isinstance(params["vlan_configs"], dict):
        cfg.setdefault("vlan_configs", {}).update(params["vlan_configs"])
        changed = True
    elif "vlan_id" in params and ("start" in params or "end" in params):
        vid = str(params["vlan_id"])
        v_cfg = cfg.setdefault("vlan_configs", {}).setdefault(vid, {})
        if "start" in params: v_cfg["start"] = params["start"]
        if "end" in params: v_cfg["end"] = params["end"]
        if "dns" in params: v_cfg["dns"] = params["dns"]
        changed = True

    if changed:
        if _save_config(cfg):
            if get_dnsmasq_pid():
                restart()
            return True, "Configuración DHCP actualizada"
        else:
            return False, "Error al guardar la configuración"
            
    return False, "No se realizaron cambios"


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
    "config": config,
    "list_leases": list_leases
}
