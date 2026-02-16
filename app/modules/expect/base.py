import os
import re
import asyncio
import tempfile
import subprocess
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

async def async_run_expect_script(script_path: str, timeout: int = 30, env_vars: Optional[Dict[str, str]] = None) -> Tuple[bool, str, str]:
    """Ejecuta un archivo de script de expect de forma asíncrona."""
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
        
        import time
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

