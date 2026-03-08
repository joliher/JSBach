import logging
import os
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
import uvicorn

# Configuración básica de log para el portal
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("portal")

app = FastAPI(title="JSBach Captive Portal")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Portal Request: {request.client.host} -> {request.url.path}")
    response = await call_next(request)
    return response

@app.api_route("/portal", methods=["GET", "HEAD"])
async def get_portal():
    file_path = "web/portal.html"
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return JSONResponse({"error": "Portal no encontrado"}, status_code=404)

@app.get("/web/css/login.css")
async def get_login_css():
    return FileResponse("web/css/login.css")
    
@app.get("/web/js/login.js")
async def get_login_js():
    return FileResponse("web/js/login.js")

@app.post("/api/portal/login")
async def portal_login(request: Request):
    try:
        data = await request.json()
        username = data.get("username")
        password = data.get("password")
        client_ip = request.client.host
        
        # Cargar helpers internamente
        from app.utils.auth_helper import authenticate_user
        portal_users_path = os.path.join(os.getcwd(), "config", "wifi", "portal_users.json")
        success, user_data = authenticate_user(username, password, portal_users_path)
        
        if success:
            import subprocess
            mac = None
            try:
                res = subprocess.check_output(["arp", "-n", client_ip], stderr=subprocess.STDOUT).decode()
                import re
                match = re.search(r'([0-9a-fA-F]{2}[:-]){5}([0-9a-fA-F]{2})', res)
                if match:
                    mac = match.group(0).lower()
            except:
                pass
            
            if not mac:
                logger.warning(f"Portal: Autenticado {username} pero no se detectó MAC de {client_ip}")
                return JSONResponse({"detail": "No se pudo identificar su dispositivo físico (MAC). Contacte con el administrador."}, status_code=400)

            from app.modules.wifi import wifi
            ok, msg = wifi.authorize_mac({"mac": mac})
            if ok:
                logger.info(f"Portal: Cliente {username} (MAC: {mac}) autorizado correctamente")
                return JSONResponse({"message": "¡Conectado! Ya puede navegar."})
            else:
                return JSONResponse({"detail": f"Error al autorizar: {msg}"}, status_code=500)
        
        return JSONResponse({"detail": "Credenciales inválidas para invitados"}, status_code=401)
    except Exception as e:
        logger.error(f"Portal login error: {e}")
        return JSONResponse({"detail": "Error en el portal de acceso"}, status_code=500)

# Catch-All para Captive Portal Detection (CPD)
@app.get("/{path:path}")
async def captive_portal_catch_all(request: Request, path: str):
    """
    Atrapa peticiones aleatorias como las de Android (generate_204) 
    o iOS (hotspot-detect.html) y fuerza un 302 hacia el portal.
    """
    # Excepciones para rutas válidas del portal
    if path.startswith("api/") or path.startswith("web/") or path == "portal":
        return JSONResponse({"detail": "Not found"}, status_code=404)
        
    wifi_ip = "10.0.99.1" # Podríamos cargarlo de config, pero por ahora hardcore para debug
    logger.info(f"CPD Interceptado: {request.client.host} -> {request.url} | Redirecting to http://{wifi_ip}:8500/portal")
    return RedirectResponse(f"http://{wifi_ip}:8500/portal", status_code=302)

