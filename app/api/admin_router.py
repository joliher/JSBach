import logging
import asyncio
import importlib
import json
import os
from typing import Optional, Any, Tuple

try:
    from fastapi import APIRouter, HTTPException, Depends, Request, Response
    from fastapi.responses import JSONResponse
except Exception:  # pragma: no cover - fallback for test environment without fastapi
    class APIRouter:
        def __init__(self, *args, **kwargs):
            pass
        def get(self, *args, **kwargs):
            def _decorator(f):
                return f
            return _decorator
        def post(self, *args, **kwargs):
            def _decorator(f):
                return f
            return _decorator

    class HTTPException(Exception):
        def __init__(self, status_code=400, detail=""):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    def Depends(x):
        return x

    class Request:
        def __init__(self):
            self.session = {}

    class Response:
        def __init__(self, content="", media_type="text/plain", status_code=200):
            self.content = content
            self.media_type = media_type
            self.status_code = status_code

try:
    from pydantic import BaseModel
except Exception:  # pragma: no cover - fallback for test environment without pydantic
    class BaseModel:  # very small fallback used only for type compatibility in tests
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

from app.utils.global_helpers import module_helpers as mh
from app.utils.global_helpers import io_helpers as ioh

router = APIRouter(prefix="/admin", tags=["admin"])

ALLOWED_MODULES = ["wan", "nat", "firewall", "vlans", "tagging", "dmz", "ebtables", "expect", "dhcp", "wifi"]

# Config directory for JSBach_V4.7
BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
CONFIG_DIR = os.path.join(BASE_DIR, "config")


# -----------------------------
# Modelos
# -----------------------------
class ModuleRequest(BaseModel):
    action: str
    params: Optional[dict[str, Any]] = None


# -----------------------------
# Estado servicios
# -----------------------------
def get_status_from_config(module_name: str) -> str:
    status = mh.get_module_status_by_name(BASE_DIR, module_name)
    if status == 0:
        return "INACTIVO"
    elif status == 1:
        return "ACTIVO"
    return "DESCONOCIDO"


# -----------------------------
# Auth dependency
# -----------------------------
def require_login(request: Request) -> str:
    logging.debug(f"Checking session for user in path: {request.url.path}")
    user = request.session.get("user")
    if not user:
        logging.debug(f"No user found in session for path: {request.url.path}")
        raise HTTPException(status_code=403, detail="Acceso denegado")
    logging.debug(f"User '{user}' authenticated.")
    return user


# -----------------------------
# Endpoints
# -----------------------------
@router.get("/status", response_model=dict[str, str])
async def get_status(_: None = Depends(require_login)):
    status_info: dict[str, str] = {}
    for module in ALLOWED_MODULES:
        status_info[module] = get_status_from_config(module)
    return status_info


@router.get("/{module_name}/info")
async def get_module_info(module_name: str, _: None = Depends(require_login)):
    """Obtener información de estado de un módulo específico."""
    if module_name not in ALLOWED_MODULES:
        raise HTTPException(status_code=404, detail="Módulo no encontrado")
    
    status = mh.get_module_status_by_name(BASE_DIR, module_name)
    return {"status": 1 if status == 1 else 0}


@router.get("/logs/{module_name}", response_class=Response)
async def get_log(module_name: str, _: None = Depends(require_login)):
    log_file = mh.get_log_file_path(BASE_DIR, module_name)
    if not os.path.exists(log_file):
        error_message = f"⚠️ El archivo de log para el módulo '{module_name}' no existe."
        return Response(content=error_message, media_type="text/plain", status_code=404)
    
    log_content = ioh.read_log_file(log_file)
    if not log_content.strip():
        log_content = "⚠️ Archivo de log vacío."
    return Response(content=log_content, media_type="text/plain")


@router.get("/config/{module_name}/{config_file}")
async def get_config_file(module_name: str, config_file: str, _: None = Depends(require_login)):
    """Servir archivos de configuración JSON de los módulos."""
    if module_name not in ALLOWED_MODULES:
        raise HTTPException(status_code=404, detail="Módulo no encontrado")
    
    if not config_file.endswith('.json'):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos JSON")
    
    file_path = os.path.join(CONFIG_DIR, module_name, config_file)
    content = ioh.read_json_file(file_path, None)
    
    if content is None:
        raise HTTPException(status_code=404, detail="Archivo no encontrado o vacío")
    return content


# -----------------------------
# Core executor
async def execute_module_action(module_name: str, action: str, params: Optional[dict] = None) -> Tuple[bool, Any]:
    if action == "start":
        deps_ok, deps_msg = mh.check_module_dependencies(BASE_DIR, module_name)
        if not deps_ok:
            error_msg = f"No se puede iniciar {module_name}: {deps_msg}"
            ioh.log_action(module_name, f"start - ERROR: {error_msg}")
            return False, error_msg
    
    if action.startswith("_"):
        ioh.log_action(module_name, f"Acción '{action}' no permitida")
        return False, "Acción no permitida"
    try:
        module = importlib.import_module(f"app.modules.{module_name}")
    except ModuleNotFoundError:
        ioh.log_action(module_name, f"Módulo '{module_name}' no encontrado")
        return False, f"Módulo '{module_name}' no encontrado"

    actions = getattr(module, "ALLOWED_ACTIONS", None)
    if not isinstance(actions, dict):
        ioh.log_action(module_name, f"Módulo '{module_name}' no expone acciones administrativas")
        return False, f"Módulo '{module_name}' no expone acciones administrativas"

    func = actions.get(action)
    if not callable(func):
        ioh.log_action(module_name, f"Acción '{action}' no permitida")
        return False, f"Acción '{action}' no permitida"

    try:
        if asyncio.iscoroutinefunction(func):
            result = await func(params)
        else:
            result = func(params)
            
        if isinstance(result, tuple) and len(result) == 2:
            success, message = result
            
            # Log filtering logic
            log_message = str(message)
            if success:
                if action == "list_switches":
                    try:
                        data = json.loads(message)
                        count = len(data.get("switches", []))
                        log_message = f"(Se listaron {count} switches, detalles ocultos por seguridad)"
                    except Exception:
                        log_message = "(Resumen no disponible, salida oculta)"
                elif log_message.startswith("{") or log_message.startswith("["):
                    if len(log_message) > 100:
                        log_message = f"(JSON extenso omitido: {len(log_message)} bytes)"

            ioh.log_action(module_name, f"{action} - {'SUCCESS' if success else 'ERROR'}: {log_message}")
            return bool(success), message
        ioh.log_action(module_name, f"Resultado inesperado de la acción '{action}'")
        return True, str(result)
    except Exception as e:
        error_message = f"Error ejecutando '{action}': {e}"
        ioh.log_action(module_name, error_message)
        return False, error_message


@router.post("/{module_name}")
async def admin_module(module_name: str, req: ModuleRequest, _: None = Depends(require_login)):
    success, message = await execute_module_action(module_name=module_name, action=req.action, params=req.params)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"success": success, "message": message}


@router.get("/expect/profiles/{profile_id}")
async def get_expect_profile(profile_id: str, _: None = Depends(require_login)):
    """Obtiene los parámetros soportados por un perfil de expect."""
    profile_path = os.path.join(CONFIG_DIR, "expect", "profiles", f"{profile_id}.json")
    if not os.path.exists(profile_path):
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    
    try:
        with open(profile_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------
# MFA Management
# -----------------------------
@router.get("/security/mfa/status")
async def get_mfa_status(request: Request, _: str = Depends(require_login)):
    user = request.session["user"]
    auth_file = os.path.join(CONFIG_DIR, "cli_users.json")
    from app.utils.auth_helper import load_users
    data = load_users(auth_file)
    for u in data.get("users", []):
        if u["username"] == user:
            return {"enabled": u.get("mfa_enabled", False)}
    return {"enabled": False}

@router.post("/security/mfa/setup")
async def setup_mfa(request: Request, _: str = Depends(require_login)):
    user = request.session["user"]
    from app.utils import mfa_helper
    secret = mfa_helper.generate_mfa_secret()
    uri = mfa_helper.get_totp_uri(user, secret)
    qr_code = mfa_helper.generate_qr_base64(uri)
    
    # IMPORTANTE: No guardamos el secreto aún como habilitado. 
    # Lo guardamos temporalmente en la sesión para el paso de verificación.
    request.session["temp_mfa_secret"] = secret
    
    return {"qr_code": qr_code, "secret": secret}

@router.post("/security/mfa/enable")
async def enable_mfa(request: Request, body: dict, _: str = Depends(require_login)):
    user = request.session["user"]
    code = body.get("code")
    secret = request.session.get("temp_mfa_secret")
    
    if not secret:
        raise HTTPException(status_code=400, detail="Debe iniciar el proceso de configuración primero")
    
    from app.utils import mfa_helper
    if mfa_helper.verify_totp_code(secret, code):
        from app.utils.auth_helper import save_mfa_secret
        auth_file = os.path.join(CONFIG_DIR, "cli_users.json")
        save_mfa_secret(user, secret, True, auth_file)
        del request.session["temp_mfa_secret"]
        return {"success": True, "message": "MFA habilitado correctamente"}
    else:
        raise HTTPException(status_code=401, detail="Código inválido")

@router.post("/security/mfa/disable")
async def disable_mfa(request: Request, body: dict, _: str = Depends(require_login)):
    user = request.session["user"]
    code = body.get("code")
    
    auth_file = os.path.join(CONFIG_DIR, "cli_users.json")
    from app.utils.auth_helper import load_users, save_mfa_secret
    data = load_users(auth_file)
    user_data = next((u for u in data.get("users", []) if u["username"] == user), None)
    
    if not user_data or not user_data.get("mfa_enabled"):
        return {"success": True, "message": "MFA ya estaba deshabilitado"}
        
    from app.utils import mfa_helper
    if mfa_helper.verify_totp_code(user_data["mfa_secret"], code):
        save_mfa_secret(user, None, False, auth_file)
        return {"success": True, "message": "MFA deshabilitado"}
    else:
        raise HTTPException(status_code=401, detail="Código inválido")
