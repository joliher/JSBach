import os
import asyncio
import subprocess
import pwd
import grp
import time
from typing import Dict, Any, Tuple, List, Optional
from app.utils.global_helpers import get_module_logger, log_action as ioh_log_action

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
LOG_DIR = os.path.join(BASE_DIR, "logs", "expect")
logger = get_module_logger("expect")

def escape_expect_send(cmd: str) -> str:
    return cmd.replace("\\", "\\\\").replace('"', '\\"')

def get_script_path(script_name: str) -> str:
    """Devuelve la ruta absoluta de un script expect."""
    return os.path.join(os.path.dirname(__file__), "scripts", f"{script_name}.exp")

def ensure_script_permissions(script_path: str):
    """Asegura que el script tenga permisos 770 y el dueño correcto (jsbach:jose o jsbach:jsbach)."""
    try:
        # Permisos 770 (rwxrwx---)
        os.chmod(script_path, 0o770)
        
        # Intentar cambiar dueño a jsbach:jose (entorno de pruebas) o jsbach:jsbach (producción)
        try:
            uid = pwd.getpwnam("jsbach").pw_uid
            # Priorizar grupo 'jose' para pruebas, luego 'jsbach' para producción
            try:
                gid = grp.getgrnam("jose").gr_gid
            except KeyError:
                gid = grp.getgrnam("jsbach").gr_gid
            
            os.chown(script_path, uid, gid)
        except (KeyError, PermissionError):
            # Si no se puede cambiar el dueño (ej. no somos root), logeamos advertencia
            logger.warning(f"No se pudo cambiar el dueño de {script_path} a jsbach:jose/jsbach. Asegúrese de que el instalador lo haga.")
            
    except Exception as e:
        logger.error(f"Error asegurando permisos en {script_path}: {e}")

async def async_run_expect_script(script_path: str, timeout: int = 30, env_vars: Optional[Dict[str, str]] = None) -> Tuple[bool, str, str]:
    """Ejecuta un archivo de script de expect de forma asíncrona."""
    # Asegurar permisos antes de ejecutar
    ensure_script_permissions(script_path)
    
    try:
        env = os.environ.copy()
        if env_vars:
            # Convertir todos los valores a string para evitar errores en subprocess
            env.update({k: str(v) for k, v in env_vars.items()})
        
        process = await asyncio.create_subprocess_exec(
            '/usr/bin/expect', script_path,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        start_time = time.time()
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=timeout)
            duration = time.time() - start_time
            stdout = stdout_bytes.decode(errors='replace')
            stderr = stderr_bytes.decode(errors='replace')
            ioh_log_action("expect", f"Script expect ejecutado en {duration:.2f}s (code {process.returncode})")
            return process.returncode == 0, stdout, stderr
        except asyncio.TimeoutError:
            process.kill()
            stdout_bytes, stderr_bytes = await process.communicate()
            duration = time.time() - start_time
            stdout = stdout_bytes.decode(errors='replace')
            stderr = stderr_bytes.decode(errors='replace')
                
            ioh_log_action("expect", f"Script expect ejecutado en {duration:.2f}s (code {process.returncode})")
            return False, stdout, "Timeout ejecutando script de expect"
            
    except Exception as e:
        logger.error(f"Error ejecutando script de expect asíncrono: {e}")
        return False, "", str(e)
    finally:
        pass

