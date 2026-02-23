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
    uvicorn.run(app, host="0.0.0.0", port=8100, log_level="info")
