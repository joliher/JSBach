import os
import logging
import asyncio
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
import uvicorn


# Load secret key
def get_secret_key():
    config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config')
    secrets_file = os.path.join(config_dir, 'secrets.env')
    
    if os.path.exists(secrets_file):
        try:
            with open(secrets_file, 'r') as f:
                for line in f:
                    if line.startswith('JSBACH_SECRET_KEY='):
                        return line.split('=', 1)[1].strip()
        except Exception:
            pass
            
    # Fallback: generate random key in memory (session will be lost on restart)
    import secrets
    logging.warning("No secrets.env found or unreadable. Using random session key (sessions will be invalid after restart).")
    return secrets.token_urlsafe(32)

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=get_secret_key(), max_age=600)

from app.utils import global_functions as gf
from app.controllers import main_controller
from app.cli import CLIServer

# Setup app immediately on import
def _setup_app():
    # Load a default config if present
    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config', 'wan.json')
    if os.path.exists(cfg_path):
        try:
            gf.load_config(cfg_path)
        except Exception:
            logging.exception("Error loading config")
    
    # Setup app routes and middleware via controller
    main_controller.setup_app(app)

_setup_app()

# CLI Server instance
cli_server = CLIServer(host="0.0.0.0", port=2200)


async def run_servers():
    """Run both web and CLI servers concurrently"""
    # Start CLI server in background
    cli_task = asyncio.create_task(cli_server.start())
    
    # Configure uvicorn for async context
    config = uvicorn.Config(app, host="0.0.0.0", port=8100, log_level="info")
    server = uvicorn.Server(config)
    
    try:
        # Run web server
        await server.serve()
    finally:
        # Cleanup CLI server on shutdown
        await cli_server.stop()


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    asyncio.run(run_servers())
