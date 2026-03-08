import logging
import os
from fastapi import Request, Depends
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from starlette.types import ASGIApp, Scope, Receive, Send
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.utils.global_helpers import io_helpers as ioh
from app.utils.auth_helper import authenticate_user

# Rutas que no requieren autenticación
PUBLIC_PATHS = {"/login", "/", "/web/css/login.css", "/web/js/login.js"}

# Configuración de Rate Limiting
limiter = Limiter(key_func=get_remote_address)

class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                # HSTS (1 año)
                headers.append((b"Strict-Transport-Security", b"max-age=31536000; includeSubDomains"))
                # Prevenir Clickjacking (Permitir el mismo origen para iframes internos)
                headers.append((b"X-Frame-Options", b"SAMEORIGIN"))
                # Prevenir MIME Sniffing
                headers.append((b"X-Content-Type-Options", b"nosniff"))
                # Referrer Policy
                headers.append((b"Referrer-Policy", b"strict-origin-when-cross-origin"))
                # CSP Básica
                csp = (
                    "default-src 'self'; "
                    "script-src 'self' 'unsafe-inline'; "
                    "style-src 'self' 'unsafe-inline'; "
                    "img-src 'self' data:; "
                    "font-src 'self'; "
                    "frame-ancestors 'self'; "
                    "form-action 'self';"
                )
                headers.append((b"Content-Security-Policy", csp.encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)

class AuthMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        path = request.url.path
        
        # 1. Rutas públicas
        if path in PUBLIC_PATHS or path.startswith("/web/css/login.css") or path.startswith("/web/js/login.js"):
            await self.app(scope, receive, send)
            return
            
        # 2. Verificar sesión
        # request.session requiere que SessionMiddleware esté por ENCIMA de este middleware
        if "user" in request.session:
            await self.app(scope, receive, send)
            return
            
        # 3. Redirigir si no está autenticado
        response = RedirectResponse("/login")
        await response(scope, receive, send)

def setup_app(app):
    """Configura rutas y eventos."""
    
    @app.on_event("startup")
    async def startup_event():
        logs_dir = os.path.join(os.getcwd(), "logs")
        ioh.clear_all_module_logs(logs_dir)
        logging.info("Logs cleared on startup (V4.5 ASGI)")

    # Registrar routers de negocio
    from . import admin_router
    app.include_router(admin_router.router)

    # El middleware de seguridad se añade aquí
    # Pero SessionMiddleware se añade en main.py DESPUÉS para que sea el primero en ejecutarse
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(AuthMiddleware)

    @app.get("/web/{full_path:path}")
    async def protected_web(full_path: str, request: Request):
        # Doble verificación (assets login)
        public_assets = {"css/login.css", "js/login.js"}
        if full_path not in public_assets and "user" not in request.session:
            return RedirectResponse("/login")
            
        file_path = os.path.join("web", full_path)
        if not os.path.exists(file_path) or os.path.isdir(file_path):
            return JSONResponse({"detail": "Recurso no encontrado"}, status_code=404)
        return FileResponse(file_path)

    @app.get("/config/{full_path:path}")
    async def protected_config(full_path: str, request: Request):
        if "user" not in request.session:
            return RedirectResponse("/login")
        file_path = os.path.join("config", full_path)
        if not os.path.exists(file_path) or os.path.isdir(file_path):
            return JSONResponse({"detail": "Archivo no encontrado"}, status_code=404)
        return FileResponse(file_path)

    @app.get("/login")
    async def get_login():
        return FileResponse("web/login.html")

    @app.post("/login")
    @limiter.limit("10/15 minute")
    async def login(request: Request):
        try:
            data = await request.json()
            username = data.get("username")
            password = data.get("password")
            mfa_code = data.get("mfa_code")
            
            auth_file = os.path.join(os.getcwd(), "config", "cli_users.json")
            success, user_data = authenticate_user(username, password, auth_file)
            
            if success:
                # Verificar si requiere MFA
                if user_data.get("mfa_enabled"):
                    if not mfa_code:
                        return JSONResponse({"mfa_required": True, "message": "MFA code required"})
                    
                    from app.utils.auth_helper import verify_mfa_code
                    if not verify_mfa_code(username, mfa_code, auth_file):
                        return JSONResponse({"detail": "Código MFA inválido"}, status_code=401)

                # Si llegamos aquí, login completo
                request.session["user"] = username
                request.session["role"] = user_data.get("role", "admin")
                logging.info(f"User {username} logged in successfully.")
                return JSONResponse({"message": "Login successful"})
            
            return JSONResponse({"detail": "Credenciales inválidas"}, status_code=401)
        except Exception as e:
            logging.error(f"Login error: {e}")
            return JSONResponse({"detail": "Error interno"}, status_code=500)

    @app.post("/logout")
    @app.get("/logout")
    async def logout(request: Request):
        request.session.clear()
        response = JSONResponse({"message": "Sesión cerrada"})
        response.delete_cookie(key="session")
        return response

    @app.get("/")
    async def root(request: Request):
        if "user" in request.session:
            return RedirectResponse("/web/index.html")
        return RedirectResponse("/login")
