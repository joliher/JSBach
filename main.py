import os
import logging
import asyncio
from fastapi import FastAPI
import uvicorn

# Load secret key
def get_secret_key():
    """Genera una clave aleatoria en memoria (las sesiones se invalidan al reiniciar)."""
    import secrets
    return secrets.token_urlsafe(32)

app = FastAPI()

# Setup app immediately on import
def _setup_app():
    from app.utils.global_helpers import io_helpers as ioh
    from app.api import main_controller
    
    # Load a default config if present
    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config', 'wan.json')
    if os.path.exists(cfg_path):
        try:
            ioh.read_json_file(cfg_path)
        except Exception:
            logging.exception("Error loading config")
    
    # Setup app routes and middleware via controller (AuthMiddleware is added here)
    main_controller.setup_app(app)
    
    # IMPORTANT: SessionMiddleware MUST be the outermost layer.
    # In FastAPI, the LAST middleware added is the FIRST to receive the request.
    from starlette.middleware.sessions import SessionMiddleware
    app.add_middleware(SessionMiddleware, secret_key=get_secret_key(), max_age=600)
    logging.info("Middleware stack initialised: [SessionMiddleware -> AuthMiddleware -> Router]")

_setup_app()

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    # El puerto principal del sistema es para la configuración y control. 
    # Sin embargo, install.py levanta la aplicación. Si PORTAL_PORT está definido,
    # este archivo debería quizás escuchar en ese puerto.
    # Actually, main.py is the primary web application. 
    # But wait, does main.py serve BOTH the admin panel AND the portal on the same port?
    # Yes, right now they are on the same port unless separate. We should bind to 80/8100 appropriately.
    # Currently it seems the installer sets system control port to `port` (e.g. 8100).
    # Since portal traffic is redirected to the router IP, it just needs to hit the FastAPI port.
    # Let's ensure the web app runs on the main `port` but we also configure the portal logic accurately later.
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8100)
    args, unknown = parser.parse_known_args()
    
    # El puerto principal del sistema viene por argumentos desde systemd
    app_port = args.port
    uvicorn.run(app, host="0.0.0.0", port=app_port, log_level="info")
