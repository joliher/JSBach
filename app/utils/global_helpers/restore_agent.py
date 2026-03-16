# app/utils/global_helpers/restore_agent.py
import os
import logging
import asyncio
import importlib
import json
from .module_helpers import load_json_config, get_config_file_path, get_module_status

logger = logging.getLogger(__name__)

async def restore_system_state(base_dir: str):
    """
    Agente de persistencia JSBach.
    Reaplica la configuración de los módulos activos en orden jerárquico.
    """
    logger.info("🟢 Agente de Restauración: Iniciando recuperación de estado...")
    
    try:
        # 0. Sitema Zero-Lockout: Asegurar configuración base de gestión
        _ensure_management_base(base_dir)
        
        # 1. Arrancar WAN (Primer paso crítico)
        await _restore_module(base_dir, "wan")
        
        # 2. ESPERA ACTIVA POR WAN (DHCP Sync)
        wan_cfg_path = get_config_file_path(base_dir, "wan")
        
        for i in range(20):
            current_status = get_module_status(wan_cfg_path)
            if current_status == 1:
                logger.info(f"✅ WAN sincronizada tras {i}s.")
                break
            # Las VLANs y Tagging pueden arrancar MIENTRAS la WAN negocia IP
            if i == 0:
                await _restore_module(base_dir, "vlans")
                await _restore_module(base_dir, "tagging")
            
            await asyncio.sleep(1)
        
        # 3. Resto de módulos que sí dependen de una WAN activa (o configurada)
        modules_to_restore = [
            "firewall", "nat", "ebtables", "dmz", "dhcp", "wifi"
        ]
        
        for module_name in modules_to_restore:
            if module_name not in ["vlans", "tagging"]:
                await _restore_module(base_dir, module_name)
        
        logger.info("✅ Agente de Restauración: Recuperación completada.")
    except Exception as e:
        logger.error(f"❌ Error crítico en el Agente de Restauración: {str(e)}")

def _ensure_management_base(base_dir: str):
    """Lógica Zero-Lockout - Crea configs de emergencia si faltan."""
    vlans_path = get_config_file_path(base_dir, "vlans")
    tagging_path = get_config_file_path(base_dir, "tagging")
    
    if not os.path.exists(vlans_path):
        logger.warning("⚠️ Zero-Lockout: Recreando vlans.json...")
        os.makedirs(os.path.dirname(vlans_path), exist_ok=True)
        with open(vlans_path, "w") as f:
            json.dump({"status": 1, "vlans": [{"id": 1, "name": "Management", "ip_interface": "192.168.1.1/24", "ip_network": "192.168.1.0/24"}]}, f, indent=4)
            
    if not os.path.exists(tagging_path):
        logger.warning("⚠️ Zero-Lockout: Recreando tagging.json...")
        wan_cfg = load_json_config(get_config_file_path(base_dir, "wan"), {})
        wan_iface = wan_cfg.get("interface")
        logical_ifaces = [i for i in os.listdir("/sys/class/net/") if i not in ["lo", "br0", wan_iface]]
        if logical_ifaces:
            main_iface = logical_ifaces[0]
            os.makedirs(os.path.dirname(tagging_path), exist_ok=True)
            with open(tagging_path, "w") as f:
                json.dump({"status": 1, "ports": {main_iface: {"pvid": 1, "untagged": [1], "tagged": []}}}, f, indent=4)

async def _restore_module(base_dir: str, module_name: str):
    """Llama a la función start() de cada módulo si está activo o es crítico."""
    try:
        config_path = get_config_file_path(base_dir, module_name)
        cfg = load_json_config(config_path, {"status": 0})
        
        if cfg.get("status") == 1 or module_name in ["wan", "vlans", "tagging"]:
            logger.info(f"🔄 Restaurando módulo: {module_name}")
            module_path = f"app.modules.{module_name}.{module_name}"
            mod = importlib.import_module(module_path)
            
            if hasattr(mod, "start"):
                func = getattr(mod, "start")
                if asyncio.iscoroutinefunction(func):
                    success, msg = await func()
                else:
                    success, msg = func()
                
                if success:
                    logger.info(f"✅ Módulo {module_name} restaurado: {msg}")
                else:
                    logger.warning(f"⚠️ Módulo {module_name} no pudo restaurarse: {msg}")
            else:
                logger.error(f"❌ Módulo {module_name} no tiene función start()")
    except Exception as e:
        logger.error(f"❌ Error restaurando {module_name}: {str(e)}")
