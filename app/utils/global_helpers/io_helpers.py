# app/core/io_helpers.py
"""
Funciones auxiliares para I/O de archivos, logs y manejo de archivos.
Centraliza escritura de logs, archivos de configuración, y gestión de directorios.
"""

import os
import logging
import json
from typing import Optional, List, Tuple


# =============================================================================
# LOGGING
# =============================================================================

def get_module_logger(module_name: str) -> logging.Logger:
    """
    Obtener o crear un logger para un módulo específico.
    """
    logger = logging.getLogger(f"jsbach.{module_name}")
    logger.setLevel(logging.DEBUG)
    return logger

def log_action(module_name: str, message: str, level: str = "INFO"):
    """Append a log message to the module's actions.log using Python logging."""
    try:
        log_file = create_module_log_directory(module_name)
        if log_file == "/dev/null":
            logging.error(f"[{module_name}] {message}")
            return

        logger = get_module_logger(module_name)
        
        # Avoid adding multiple handlers
        if not any(isinstance(h, logging.FileHandler) and getattr(h, 'baseFilename', None) == os.path.abspath(log_file) for h in logger.handlers):
            fh = logging.FileHandler(log_file)
            fh.setLevel(logging.DEBUG)
            fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%d/%m/%Y %H:%M:%S')
            fh.setFormatter(fmt)
            logger.addHandler(fh)

        level = (level or "INFO").upper()
        log_func = getattr(logger, level.lower(), logger.info)
        log_func(message)
        
        # Legacy raw write
        with open(log_file, 'a') as f:
            f.write('\n')
            
    except Exception as e:
        logging.error(f"Error logging action for {module_name}: {e}. Original message: {message}")

def clear_all_module_logs(logs_directory: str):
    """Limpiar todos los logs de módulos."""
    if not os.path.isdir(logs_directory):
        return
    for module_name in os.listdir(logs_directory):
        module_log_dir = os.path.join(logs_directory, module_name)
        log_file = os.path.join(module_log_dir, "actions.log")
        if os.path.exists(log_file):
            clear_log_file(log_file)


def write_log_file(file_path: str, message: str, append: bool = True) -> bool:
    """
    Escribir mensaje en archivo de log.
    
    Args:
        file_path: Ruta al archivo de log
        message: Mensaje a escribir
        append: True para append, False para sobrescribir
    
    Returns:
        True si se escribió exitosamente
    """
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        mode = "a" if append else "w"
        
        with open(file_path, mode) as f:
            if append:
                f.write(message + "\n")
            else:
                f.write(message)
        
        return True
    except Exception as e:
        logging.error(f"Error escribiendo log en {file_path}: {e}")
        return False


def clear_log_file(file_path: str) -> bool:
    """
    Limpiar contenido de archivo de log.
    
    Args:
        file_path: Ruta al archivo de log
    
    Returns:
        True si se limpió exitosamente
    """
    try:
        with open(file_path, "w") as f:
            pass
        return True
    except Exception as e:
        logging.error(f"Error limpiando log {file_path}: {e}")
        return False


def read_log_file(file_path: str, lines: Optional[int] = None) -> str:
    """
    Leer contenido de archivo de log.
    
    Args:
        file_path: Ruta al archivo de log
        lines: Si se especifica, retorna solo las últimas N líneas
    
    Returns:
        Contenido del archivo
    """
    if not os.path.exists(file_path):
        return "(log file not found)"
    
    try:
        with open(file_path, "r") as f:
            content = f.read()
        
        if lines is not None and lines > 0:
            log_lines = content.split("\n")
            return "\n".join(log_lines[-lines:])
        
        return content
    except Exception as e:
        return f"Error leyendo log: {e}"


# =============================================================================
# MANEJO DE DIRECTORIOS
# =============================================================================

def ensure_directory_exists(dir_path: str) -> bool:
    """
    Asegurar que un directorio existe, creándolo si es necesario.
    
    Args:
        dir_path: Ruta del directorio
    
    Returns:
        True si existe o fue creado exitosamente
    """
    try:
        os.makedirs(dir_path, exist_ok=True)
        return True
    except Exception as e:
        logging.error(f"Error creando directorio {dir_path}: {e}")
        return False


def ensure_file_exists(file_path: str, default_content: str = "") -> bool:
    """
    Asegurar que un archivo existe, creándolo si es necesario.
    """
    if os.path.exists(file_path):
        return True
    
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w") as f:
            f.write(default_content)
        return True
    except Exception as e:
        logging.error(f"Error creando archivo {file_path}: {e}")
        return False

def get_base_dir() -> str:
    """Obtener el directorio base del proyecto."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

def create_module_log_directory(module_name: str) -> str:
    """Crea y retorna la ruta al actions.log del módulo."""
    base_dir = get_base_dir()
    log_dir = os.path.join(base_dir, "logs", module_name)
    log_file = os.path.join(log_dir, "actions.log")
    
    try:
        os.makedirs(log_dir, exist_ok=True)
        if not os.path.exists(log_file):
            with open(log_file, "w"):
                pass
    except (PermissionError, OSError) as e:
        logging.error(f"Error creando directorio de logs para {module_name}: {e}")
        return "/dev/null"
        
    return log_file

def ensure_module_config_directory(module_name: str) -> str:
    """Asegura que existe el directorio de configuración del módulo."""
    base_dir = get_base_dir()
    config_dir = os.path.join(base_dir, "config", module_name)
    os.makedirs(config_dir, exist_ok=True)
    return config_dir


def list_directory_files(dir_path: str, extension: Optional[str] = None) -> List[str]:
    """
    Listar archivos en un directorio.
    
    Args:
        dir_path: Ruta del directorio
        extension: Si se especifica, filtrar por extensión (ej: ".json")
    
    Returns:
        Lista de nombres de archivo
    """
    if not os.path.exists(dir_path) or not os.path.isdir(dir_path):
        return []
    
    try:
        files = os.listdir(dir_path)
        
        if extension:
            files = [f for f in files if f.endswith(extension)]
        
        return files
    except Exception as e:
        logging.error(f"Error listando directorio {dir_path}: {e}")
        return []


def remove_file(file_path: str) -> bool:
    """
    Eliminar un archivo.
    
    Args:
        file_path: Ruta del archivo
    
    Returns:
        True si se eliminó exitosamente
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
        return True
    except Exception as e:
        logging.error(f"Error eliminando archivo {file_path}: {e}")
        return False


# =============================================================================
# MANEJO DE ARCHIVOS JSON
# =============================================================================

def write_json_file(file_path: str, data: dict, pretty: bool = True) -> bool:
    """
    Escribir datos en archivo JSON.
    
    Args:
        file_path: Ruta del archivo
        data: Datos a escribir (dict)
        pretty: Si True, formatea el JSON
    
    Returns:
        True si se escribió exitosamente
    """
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, "w") as f:
            if pretty:
                json.dump(data, f, indent=4)
            else:
                json.dump(data, f)
        
        return True
    except Exception as e:
        logging.error(f"Error escribiendo JSON en {file_path}: {e}")
        return False


def read_json_file(file_path: str, default: Optional[dict] = None) -> dict:
    """
    Leer datos de archivo JSON.
    
    Args:
        file_path: Ruta del archivo
        default: Valor por defecto si no existe o hay error
    
    Returns:
        Dict con los datos
    """
    if default is None:
        default = {}
    
    if not os.path.exists(file_path):
        return default
    
    try:
        with open(file_path, "r") as f:
            content = f.read().strip()
            if not content:
                return default
            return json.loads(content)
    except json.JSONDecodeError as e:
        logging.error(f"Error decodificando JSON en {file_path}: {e}")
        return default
    except Exception as e:
        logging.error(f"Error leyendo JSON en {file_path}: {e}")
        return default


# =============================================================================
# OPERACIONES DE ARCHIVOS EN BATCH
# =============================================================================

def backup_file(file_path: str, suffix: str = ".bak") -> Tuple[bool, str]:
    """
    Crear backup de un archivo.
    
    Args:
        file_path: Ruta del archivo a respaldar
        suffix: Sufijo para el archivo backup
    
    Returns:
        Tuple[success, backup_path or error_message]
    """
    if not os.path.exists(file_path):
        return False, f"Archivo no existe: {file_path}"
    
    backup_path = file_path + suffix
    
    try:
        with open(file_path, "r") as src:
            with open(backup_path, "w") as dst:
                dst.write(src.read())
        return True, backup_path
    except Exception as e:
        return False, f"Error creando backup: {e}"


def restore_from_backup(backup_path: str, original_path: str) -> bool:
    """
    Restaurar archivo desde backup.
    
    Args:
        backup_path: Ruta del backup
        original_path: Ruta donde restaurar
    
    Returns:
        True si se restauró exitosamente
    """
    if not os.path.exists(backup_path):
        logging.error(f"Backup no existe: {backup_path}")
        return False
    
    try:
        with open(backup_path, "r") as src:
            with open(original_path, "w") as dst:
                dst.write(src.read())
        return True
    except Exception as e:
        logging.error(f"Error restaurando desde backup: {e}")
        return False


def cleanup_old_logs(log_dir: str, keep_files: int = 5) -> int:
    """
    Limpiar archivos de log antiguos, manteniendo solo los N más recientes.
    
    Args:
        log_dir: Directorio de logs
        keep_files: Número de archivos a mantener
    
    Returns:
        Número de archivos eliminados
    """
    if not os.path.exists(log_dir):
        return 0
    
    try:
        files = [os.path.join(log_dir, f) for f in os.listdir(log_dir)]
        files = [f for f in files if os.path.isfile(f)]
        
        if len(files) <= keep_files:
            return 0
        
        # Ordenar por fecha de modificación, mantener los más nuevos
        files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
        files_to_remove = files[keep_files:]
        
        removed = 0
        for f in files_to_remove:
            try:
                os.remove(f)
                removed += 1
            except Exception:
                pass
        
        return removed
    except Exception as e:
        logging.error(f"Error limpiando logs antiguos: {e}")
        return 0
