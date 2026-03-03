# app/modules/wifi/monitor.py
import subprocess
import os
import sys
import logging
import time
import re

# Configuración básica de log
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("wifi_monitor")

# Añadir el raíz del proyecto al path para importar módulos
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.append(BASE_DIR)

from app.modules.wifi import wifi
from app.utils.global_helpers import load_json_config

CONFIG_DIR = os.path.join(BASE_DIR, "config", "wifi")
CONFIG_FILE = os.path.join(CONFIG_DIR, "wifi.json")

def handle_event(event_str):
    """Procesa una línea de evento de hostapd."""
    event_str = event_str.strip()
    if not event_str:
        return

    logger.debug(f"Procesando línea: {event_str}")
    
    # Evento típico: <3>AP-STA-DISCONNECTED 22:ac:a4:56:c6:3a
    if "AP-STA-DISCONNECTED" in event_str:
        match = re.search(r'([0-9a-fA-F]{2}[:-]){5}([0-9a-fA-F]{2})', event_str)
        if match:
            mac = match.group(0).lower()
            logger.info(f"¡Desconexión detectada! MAC: {mac}. Revocando acceso...")
            success, message = wifi.deauthorize_mac({"mac": mac})
            if success:
                logger.info(f"Acceso revocado para {mac}: {message}")
            else:
                if "no estaba autorizado" in message.lower():
                    logger.info(f"La MAC {mac} no tenía sesión activa.")
                else:
                    logger.error(f"Error al revocar acceso para {mac}: {message}")
        else:
            logger.warning(f"Se detectó desconexión pero no se pudo extraer la MAC: {event_str}")

def monitor_events():
    """Escucha eventos de hostapd_cli usando stdbuf para evitar problemas de buffer."""
    wifi_cfg = load_json_config(CONFIG_FILE, {})
    iface = wifi_cfg.get("interface", "wlp3s0")
    
    logger.info(f"Iniciando monitoreo de eventos en interfaz {iface} con stdbuf...")
    
    # Usamos stdbuf -oL para forzar el buffer de línea en la salida estándar de hostapd_cli
    cmd = ["/usr/bin/stdbuf", "-oL", "/usr/sbin/hostapd_cli", "-i", iface]
    
    try:
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True, 
            bufsize=1,
            universal_newlines=True
        )
        
        logger.info(f"Proceso hostapd_cli (PID: {process.pid}) iniciado exitosamente.")
        
        while True:
            line = process.stdout.readline()
            if not line:
                if process.poll() is not None:
                    logger.warning("hostapd_cli se ha detenido inesperadamente.")
                    break
                time.sleep(0.1)
                continue
            
            handle_event(line)

    except Exception as e:
        logger.error(f"Error fatal en el monitor: {e}")
        time.sleep(5)
        sys.exit(1)
    finally:
        if 'process' in locals() and process.poll() is None:
            process.terminate()
            logger.info("Monitor detenido.")

if __name__ == "__main__":
    monitor_events()
