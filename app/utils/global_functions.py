import json
import logging
import os


def check_module_dependencies(module_name: str = None) -> tuple:
    """
    Verifica dependencias jerárquicas de un módulo.
    Jerarquía: WAN -> VLANs -> Tagging -> [Firewall, Ebtables, DMZ]
    DMZ requiere Firewall adicionalmente.
    """
    if module_name is None:
        return True, "Dependencias satisfechas"

    # 0. WAN no tiene dependencias
    if module_name == "wan":
        return True, "Dependencias satisfechas"

    # 1. WAN es la base de todo (para otros módulos)
    if get_module_status("wan") != 1:
        return False, "Error: El módulo WAN debe estar activo."

    # 2. VLANs requiere WAN (ya chequeado)
    if module_name == "vlans":
        return True, "Dependencias satisfechas"

    # 3. Tagging, Firewall, Ebtables, DMZ requieren VLANs
    if get_module_status("vlans") != 1:
        return False, "Error: El módulo VLANs debe estar activo."
        
    if module_name == "tagging":
        return True, "Dependencias satisfechas"

    # 4. Firewall, Ebtables, DMZ requieren Tagging
    if get_module_status("tagging") != 1:
        return False, "Error: El módulo Tagging debe estar activo."

    if module_name in ["firewall", "ebtables"]:
        return True, "Dependencias satisfechas"

    # 5. DMZ requiere Firewall
    if module_name == "dmz":
        if get_module_status("firewall") != 1:
            return False, "Error: El módulo Firewall debe estar activo para usar DMZ."

    return True, "Dependencias satisfechas"

GLOBAL_CONFIG = {}

def load_config(path):
    """Load JSON config into GLOBAL_CONFIG and return it."""
    if not os.path.exists(path):
        logging.warning(f"Config file not found: {path}")
        return {}
    with open(path, 'r') as f:
        data = json.load(f)
    GLOBAL_CONFIG.update(data)
    return GLOBAL_CONFIG

def clear_logs(logs_directory):
    """Clear action logs inside `logs_directory/<module>/actions.log`"""
    if not os.path.isdir(logs_directory):
        logging.warning(f"Logs directory not found: {logs_directory}")
        return
    for module_name in os.listdir(logs_directory):
        module_log_dir = os.path.join(logs_directory, module_name)
        log_file = os.path.join(module_log_dir, "actions.log")
        if os.path.exists(log_file):
            try:
                with open(log_file, 'w'):
                    pass
                logging.info(f"Cleared log for module {module_name}")
            except Exception as e:
                logging.error(f"Error clearing log for {module_name}: {e}")

def get(key, default=None):
    return GLOBAL_CONFIG.get(key, default)


def create_module_log_directory(module_name: str) -> str:
    """Create and return path to module's actions.log under project's `logs` dir."""
    # Usar ruta absoluta basada en la ubicación del proyecto
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    log_dir = os.path.join(base_dir, "logs", module_name)
    log_file = os.path.join(log_dir, "actions.log")
    
    try:
        os.makedirs(log_dir, exist_ok=True)
        if not os.path.exists(log_file):
            with open(log_file, "w"):
                pass
    except (PermissionError, OSError) as e:
        # Si falla por permisos, devolvemos /dev/null o una ruta temporal para no romper la app
        logging.error(f"Error creando directorio de logs para {module_name}: {e}")
        return "/dev/null"
        
    return log_file


def create_module_config_directory(module_name: str) -> str:
    """Create and return path to module's config directory under project's `config` dir."""
    # Usar ruta absoluta basada en la ubicación del proyecto
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    config_dir = os.path.join(base_dir, "config", module_name)
    try:
        os.makedirs(config_dir, exist_ok=True)
    except (PermissionError, OSError) as e:
        logging.error(f"Error creando directorio de config para {module_name}: {e}")
        # Retornamos el path de todas formas, el error saltará al intentar escribir archivo
    return config_dir


def log_action(module_name: str, message: str, level: str = "INFO"):
    """Append a log message to the module's actions.log using Python logging.

    Levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
    """
    try:
        log_file = create_module_log_directory(module_name)
        
        # Si log_file es /dev/null, usar logger root solo
        if log_file == "/dev/null":
            logging.error(f"[{module_name}] {message}")
            return

        logger = logging.getLogger(f"jsbach.{module_name}")
        logger.setLevel(logging.DEBUG)
        # Avoid adding multiple handlers in long-running processes
        if not any(isinstance(h, logging.FileHandler) and getattr(h, 'baseFilename', None) == os.path.abspath(log_file) for h in logger.handlers):
            fh = logging.FileHandler(log_file)
            fh.setLevel(logging.DEBUG)
            fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%d/%m/%Y %H:%M:%S')
            fh.setFormatter(fmt)
            logger.addHandler(fh)

        level = (level or "INFO").upper()
        if level == "DEBUG":
            logger.debug(message)
        elif level == "WARNING":
            logger.warning(message)
        elif level == "ERROR":
            logger.error(message)
        elif level == "CRITICAL":
            logger.critical(message)
        else:
            logger.info(message)
        
        # Escritura manual raw al archivo (legacy support/redundancia)
        with open(log_file, 'a') as f:
            f.write('\n')
            
    except (PermissionError, OSError) as e:
        # Fallback a logging standard si falla el archivo específico
        logging.error(f"Error logging action for {module_name}: {e}. Original message: {message}")


def get_module_status(module_name: str) -> int:
    """Get module status from its config file. Returns 1 if active, 0 if inactive."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    config_file = os.path.join(base_dir, "config", module_name, f"{module_name}.json")
    
    if not os.path.exists(config_file):
        return 0
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        return config.get("status", 0)
    except Exception:
        return 0
