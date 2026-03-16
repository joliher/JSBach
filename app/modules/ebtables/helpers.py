# app/core/helpers/helper_ebtables.py
# Helper functions para el módulo Ebtables (aislamiento L2)

import subprocess
import json
import os
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
import logging
import re
from typing import Dict, Any, Tuple, List
from ...utils.global_helpers import (
    module_helpers as mh,
    io_helpers as ioh
)
from ...utils.validators import validate_interface_name
from ...utils.global_helpers import (
    load_json_config,
    save_json_config
)
from ..tagging.helpers import parse_vlan_range

# Configurar logging
logger = logging.getLogger(__name__)

# Rutas de configuración
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
EBTABLES_CONFIG_FILE = os.path.join(BASE_DIR, "config", "ebtables", "ebtables.json")
VLANS_CONFIG_FILE = os.path.join(BASE_DIR, "config", "vlans", "vlans.json")
WAN_CONFIG_FILE = os.path.join(BASE_DIR, "config", "wan", "wan.json")
TAGGING_CONFIG_FILE = os.path.join(BASE_DIR, "config", "tagging", "tagging.json")


# =============================================================================
# UTILIDADES BÁSICAS
# =============================================================================

def ensure_dirs():
    """Crear directorios necesarios para configuración y logs."""
    os.makedirs(os.path.dirname(EBTABLES_CONFIG_FILE), exist_ok=True)
    ioh.create_module_log_directory("ebtables")
    ioh.ensure_module_config_directory("ebtables")


def load_ebtables_config() -> dict:
    """Cargar configuración de ebtables."""
    return load_json_config(EBTABLES_CONFIG_FILE, {"vlans": {}, "status": 0, "wifi": {"isolated": False}})

def load_wifi_config() -> Dict[str, Any]:
    """Cargar configuración de Wi-Fi."""
    WIFI_CONFIG_FILE = os.path.join(BASE_DIR, "config", "wifi", "wifi.json")
    return load_json_config(WIFI_CONFIG_FILE, {})


def save_ebtables_config(data: dict):
    """Guardar configuración de ebtables."""
    success = save_json_config(EBTABLES_CONFIG_FILE, data)
    if not success:
        logger.warning(f"No se pudo guardar ebtables config en {EBTABLES_CONFIG_FILE}")
    return success


def load_vlans_config() -> dict:
    """Cargar configuración de VLANs desde vlans.json."""
    if not os.path.exists(VLANS_CONFIG_FILE):
        return {"vlans": [], "status": 0}
    try:
        with open(VLANS_CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error cargando VLANs config: {e}")
        return {"vlans": [], "status": 0}


def load_wan_config() -> dict:
    """Cargar configuración de WAN."""
    if not os.path.exists(WAN_CONFIG_FILE):
        return None
    try:
        with open(WAN_CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error cargando WAN config: {e}")
        return None


def load_tagging_config() -> dict:
    """Cargar configuración de tagging desde tagging.json."""
    if not os.path.exists(TAGGING_CONFIG_FILE):
        return {"interfaces": [], "status": 0}
    try:
        with open(TAGGING_CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error cargando tagging config: {e}")
        return {"interfaces": [], "status": 0}


def validate_wan_interface(wan_iface: str) -> Tuple[bool, str]:
    """Validar que la interfaz WAN sea segura y exista en el sistema."""
    if not wan_iface:
        return False, "Interfaz WAN no encontrada"

    valid, error = validate_interface_name(wan_iface)
    if not valid:
        return False, f"Interfaz WAN inválida: {error}"

    if not os.path.exists(f"/sys/class/net/{wan_iface}"):
        return False, f"Interfaz WAN no existe: {wan_iface}"

    return True, ""


def build_vlan_interface_map(vlans: List[dict], tagging_cfg: dict) -> Dict[int, List[str]]:
    """Construir mapa VLAN → interfaces físicas.
    
    Retorna: {vlan_id: [lista de interfaces en esa VLAN]}
    
    Valida que todas las VLANs en tagging.json existan realmente en vlans.json
    """
    # Crear set de VLANs válidas
    valid_vlan_ids = {vlan.get("id") for vlan in vlans if vlan.get("id") is not None}
    
    # Inicializar mapa vacío para todas las VLANs válidas
    vlan_iface_map: Dict[int, List[str]] = {vlan_id: [] for vlan_id in valid_vlan_ids}
    
    # Procesar cada interfaz en tagging.json
    for iface in tagging_cfg.get("interfaces", []):
        iface_name = iface.get("name", "")
        
        # Procesar VLANs untagged
        vlan_untag = iface.get("vlan_untag", "").strip()
        if vlan_untag:
            try:
                vlan_id = int(vlan_untag)
                if vlan_id in valid_vlan_ids:
                    if iface_name not in vlan_iface_map[vlan_id]:
                        vlan_iface_map[vlan_id].append(iface_name)
                    logger.info(f"Interfaz {iface_name} → VLAN {vlan_id} (untagged)")
                else:
                    logger.warning(f"VLAN {vlan_id} en tagging.json NO existe en vlans.json")
            except (ValueError, TypeError):
                logger.warning(f"VLAN untagged inválida en interfaz {iface_name}: {vlan_untag}")
        
        # Procesar VLANs tagged
        vlan_tag_str = iface.get("vlan_tag", "").strip()
        if vlan_tag_str:
            tag_list = parse_vlan_range(vlan_tag_str)
            if not tag_list:
                logger.warning(f"VLAN tagged inválida en interfaz {iface_name}: {vlan_tag_str}")
                continue

            for vlan_id_str in tag_list:
                try:
                    vlan_id = int(vlan_id_str)
                    if vlan_id in valid_vlan_ids:
                        if iface_name not in vlan_iface_map[vlan_id]:
                            vlan_iface_map[vlan_id].append(iface_name)
                        logger.info(f"Interfaz {iface_name} → VLAN {vlan_id} (tagged)")
                    else:
                        logger.warning(f"VLAN {vlan_id} en tagging.json NO existe en vlans.json")
                except (ValueError, TypeError):
                    logger.warning(f"VLAN tagged inválida en interfaz {iface_name}: {vlan_id_str}")
    
    return vlan_iface_map


def check_wan_active() -> Tuple[bool, str]:
    """Verificar si la WAN está activa y obtener la interfaz."""
    wan_cfg = load_wan_config()
    if not wan_cfg:
        return False, None
    
    if wan_cfg.get("status") != 1:
        return False, None
    
    iface = wan_cfg.get("interface")
    if not iface:
        return False, None
    
    return True, iface


def check_vlans_active() -> Tuple[bool, str]:
    """Verificar si el módulo VLANs está activo."""
    vlans_cfg = load_vlans_config()
    if not vlans_cfg:
        return False, "Módulo VLANs no configurado"
    
    status = vlans_cfg.get("status", 0)
    if status != 1:
        return False, "Módulo VLANs no está activo"
    
    vlans = vlans_cfg.get("vlans", [])
    if not vlans:
        return False, "No hay VLANs configuradas"
    
    return True, None


def check_tagging_active() -> Tuple[bool, str]:
    """Verificar si el módulo Tagging está activo."""
    tagging_cfg = load_tagging_config()
    if not tagging_cfg:
        return False, "Módulo Tagging no configurado"
    
    status = tagging_cfg.get("status", 0)
    if status != 1:
        return False, "Módulo Tagging no está activo"
    
    interfaces = tagging_cfg.get("interfaces", [])
    if not interfaces:
        return False, "No hay interfaces configuradas en Tagging"
    
    return True, None


def check_interface_vlan_conflict(vlan_id: int, vlan_interfaces: List[str], tagging_cfg: dict) -> Tuple[bool, str]:
    """Validar que las interfaces no causen conflicto de VLANs.
    
    Reglas:
    - Una interfaz en modo UNTAGGED puede estar SOLO en una VLAN
    - Una interfaz en modo TAGGED puede estar en múltiples VLANs
    
    Args:
        vlan_id: ID de la VLAN a validar
        vlan_interfaces: Interfaces que van a aislarse para esta VLAN
        tagging_cfg: Configuración de tagging.json
    
    Returns:
        (True, "") si no hay conflictos
        (False, mensaje_error) si hay conflicto
    """
    # Crear mapa de interfaz → (vlan_untag, vlan_tag)
    iface_vlan_map = {}
    for iface in tagging_cfg.get("interfaces", []):
        iface_name = iface.get("name", "")
        vlan_untag = iface.get("vlan_untag", "").strip()
        vlan_tag = iface.get("vlan_tag", "").strip()
        
        if iface_name:
            iface_vlan_map[iface_name] = {
                "untag": int(vlan_untag) if vlan_untag else None,
                "tag": [int(v.strip()) for v in vlan_tag.split(",") if v.strip()] if vlan_tag else []
            }
    
    # Validar cada interfaz de la VLAN
    for iface in vlan_interfaces:
        if iface not in iface_vlan_map:
            # Interfaz no en tagging.json - considerar error
            return False, f"Interfaz {iface} no está configurada en tagging.json"
        
        iface_config = iface_vlan_map[iface]
        
        # Si está en modo UNTAGGED
        if iface_config["untag"] is not None:
            # Debe estar SOLO en una VLAN
            if iface_config["untag"] != vlan_id:
                return False, (
                    f"Conflicto: Interfaz {iface} está en VLAN {iface_config['untag']} (UNTAGGED). "
                    f"Una interfaz UNTAGGED no puede estar en múltiples VLANs. "
                    f"Está intentando añadirla a VLAN {vlan_id}."
                )
        else:
            # Si no tiene UNTAGGED, debe estar en TAGGED
            # Pero vlan_id debe estar en su lista de VLANs TAGGED
            if vlan_id not in iface_config["tag"]:
                return False, (
                    f"Conflicto: Interfaz {iface} no está configurada para VLAN {vlan_id}. "
                    f"VLANs TAGGED configuradas: {iface_config['tag']}"
                )
    
    return True, ""


def check_vlan_already_isolated(vlan_id: int, ebtables_cfg: dict) -> Tuple[bool, str]:
    """Validar que una VLAN no sea aislada dos veces (evita sobrescrituras).
    
    Args:
        vlan_id: ID de la VLAN a validar
        ebtables_cfg: Configuración actual de ebtables.json
    
    Returns:
        (True, "") si la VLAN no está aislada
        (False, mensaje_error) si ya está aislada
    """
    vlans = ebtables_cfg.get("vlans", {})
    vlan_id_str = str(vlan_id)
    
    if vlan_id_str in vlans:
        vlan_data = vlans[vlan_id_str]
        if vlan_data.get("isolated") == True:
            return False, (
                f"VLAN {vlan_id} ya está aislada. "
                f"Para cambiar su configuración, primero desaísla con: /unisolate {vlan_id}"
            )
    
    return True, ""


def check_dependencies() -> Tuple[bool, str]:
    """Verificar que todos los módulos requeridos estén activos.
    
    Returns:
        (True, None) si todo ok
        (False, mensaje_error) si falta alguno
    """
    # Verificar WAN
    wan_active, _ = check_wan_active()
    if not wan_active:
        return False, "Módulo WAN debe estar activo"
    
    # Verificar VLANs
    vlans_ok, vlans_msg = check_vlans_active()
    if not vlans_ok:
        return False, vlans_msg
    
    # Verificar Tagging
    tagging_ok, tagging_msg = check_tagging_active()
    if not tagging_ok:
        return False, tagging_msg
    
    return True, None


def update_status(status: int) -> None:
    """Actualizar el estado del módulo (0=inactivo, 1=activo)."""
    cfg = load_ebtables_config()
    cfg["status"] = status
    save_ebtables_config(cfg)


def run_ebtables(args: List[str], timeout: int = 30) -> Tuple[bool, str]:
    """Ejecutar comando ebtables."""
    try:
        result = subprocess.run(
            ["sudo", "/usr/sbin/ebtables"] + args,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        if result.returncode == 0:
            return True, result.stdout
        return False, result.stderr
    except subprocess.TimeoutExpired:
        return False, "Timeout ejecutando ebtables"
    except Exception as e:
        return False, str(e)


# =============================================================================
# GESTIÓN DE CADENAS
# =============================================================================

def create_vlan_chain(vlan_id: Any) -> bool:
    """Crear cadena para una VLAN específica o Wi-Fi."""
    chain_name = f"FORWARD_VLAN_{vlan_id}" if str(vlan_id).isdigit() else f"FORWARD_{str(vlan_id).upper()}"
    
    # Verificar si ya existe
    success, _ = run_ebtables(["-L", chain_name])
    if success:
        logger.info(f"Cadena {chain_name} ya existe")
        return True
    
    # Crear la cadena
    success, msg = run_ebtables(["-N", chain_name])
    if not success:
        logger.error(f"Error creando cadena {chain_name}: {msg}")
        return False
    
    logger.info(f"Cadena {chain_name} creada")
    return True


def delete_vlan_chain(vlan_id: Any) -> bool:
    """Eliminar cadena de una VLAN o Wi-Fi."""
    chain_name = f"FORWARD_VLAN_{vlan_id}" if str(vlan_id).isdigit() else f"FORWARD_{str(vlan_id).upper()}"
    
    # Verificar si existe
    success, output = run_ebtables(["-L", chain_name])
    if not success:
        return True  # No existe, no hay que hacer nada
    
    # Flush de reglas primero (elimina todas: WAN ACCEPT y DROP)
    logger.info(f"Eliminando reglas de {chain_name} (WAN ACCEPT y DROP)...")
    run_ebtables(["-F", chain_name])
    
    # Eliminar referencias en FORWARD (todas las que redireccionan a esta cadena)
    success, output = run_ebtables(["-L", "FORWARD", "--Ln"])
    if success:
        # Buscar reglas que salten a esta cadena (-j FORWARD_VLAN_X)
        lines = output.strip().split('\n')
        for line in lines:
            if f"-j {chain_name}" in line:
                # Extraer interfaz de entrada (-i)
                if "-i " in line:
                    parts = line.split("-i ")
                    if len(parts) > 1:
                        iface = parts[1].split()[0]
                        run_ebtables(["-D", "FORWARD", "-i", iface, "-j", chain_name])
    
    # Eliminar la cadena
    success, msg = run_ebtables(["-X", chain_name])
    if not success:
        logger.error(f"Error eliminando cadena {chain_name}: {msg}")
        return False
    
    logger.info(f"Cadena {chain_name} eliminada")
    return True


def add_vlan_interface_to_forward(vlan_id: Any, _iface=None, _priority=1) -> bool:
    """Agregar regla en FORWARD que redirecciona tráfico VLAN/Wi-Fi a su cadena."""
    chain_name = f"FORWARD_VLAN_{vlan_id}" if str(vlan_id).isdigit() else f"FORWARD_{str(vlan_id).upper()}"
    mh.ensure_ebtables_global_chains()
    return mh.ensure_module_hook("filter", "JSB_GLOBAL_EBT_ISOLATE", chain_name, binary="ebtables")


def remove_vlan_interface_from_forward(vlan_interface: str) -> bool:
    """Remover reglas de FORWARD que redireccionan interfaz VLAN."""
    # Obtener todas las reglas de FORWARD
    success, output = run_ebtables(["-L", "FORWARD", "--Ln"])
    if not success:
        return True
    
    # Buscar y eliminar reglas con esta interfaz
    lines = output.strip().split('\n')
    rules_removed = False
    for line in lines:
        if f"-i {vlan_interface}" in line:
            # Extraer el target (cadena destino)
            # Formato: -i enxXXX -j FORWARD_VLAN_X
            if "-j FORWARD_VLAN_" in line:
                chain_target = line.split("-j")[-1].strip()
                # Verificar que la regla existe antes de eliminar
                verify_success, verify_output = run_ebtables(["-L", "FORWARD", "--Ln"])
                if verify_success and f"-i {vlan_interface} -j {chain_target}" in verify_output:
                    run_ebtables(["-D", "FORWARD", "-i", vlan_interface, "-j", chain_target])
                    rules_removed = True
                    logger.info(f"Regla FORWARD -i {vlan_interface} -j {chain_target} eliminada")
    
    if not rules_removed:
        logger.info(f"No se encontraron reglas FORWARD para {vlan_interface}")
    return True


def apply_isolation(vlan_id: int, wan_iface: str, vlan_interfaces: List[str]) -> bool:
    """Aplicar aislamiento a una VLAN (solo permite tráfico con WAN).
    
    Estructura optimizada:
    FORWARD:
      -i <interfaz_vlan> -j FORWARD_VLAN_X    (redirecciona tráfico de la interfaz VLAN)
      ...
      -j DROP                                   (rechaza todo lo demás)
    
    FORWARD_VLAN_X:
      -i <interfaz_wan> -j ACCEPT              (permite entrada WAN)
      -o <interfaz_wan> -j ACCEPT              (permite salida WAN)
      -j DROP                                   (bloquea todo lo demás - aislamiento entre VLANs)
    
    Args:
        vlan_id: ID de la VLAN
        wan_iface: Interfaz WAN (ej: eth0)
        vlan_interfaces: Lista de interfaces físicas en esta VLAN
    """
    chain_name = f"FORWARD_VLAN_{vlan_id}" if str(vlan_id).isdigit() else f"FORWARD_{str(vlan_id).upper()}"
    
    # Validar conflictos de VLANs antes de aplicar aislamiento (solo para VLANs numéricas)
    if str(vlan_id).isdigit():
        tagging_cfg = load_tagging_config()
        conflict_ok, conflict_msg = check_interface_vlan_conflict(int(vlan_id), vlan_interfaces, tagging_cfg)
        if not conflict_ok:
            logger.error(f"Conflicto de VLAN: {conflict_msg}")
            return False
    
    logger.info(f"Aplicando aislamiento a {vlan_id} - Interfaces: {vlan_interfaces}")
    
    # Asegurar que la cadena existe
    # create_vlan_chain usa f"FORWARD_VLAN_{vlan_id}" internamente. 
    # Mejor refactorizar create_vlan_chain o usar una lógica consistente.
    if not create_vlan_chain(vlan_id):
        logger.error(f"No se pudo crear cadena {chain_name}")
        return False
    
    # Flush de reglas existentes en la cadena VLAN
    success, msg = run_ebtables(["-F", chain_name])
    if not success:
        logger.warning(f"Advertencia al limpiar {chain_name}: {msg}")
    else:
        logger.info(f"Reglas previas de {chain_name} eliminadas")
    
    # En FORWARD_VLAN_X, agregar solo reglas WAN (entrada y salida)
    
    # Regla 1: Permitir tráfico ENTRADA desde WAN (RETURN para dejar que otros judguen)
    # Verificar si ya existe antes de añadir
    verify_success, verify_output = run_ebtables(["-L", chain_name, "--Ln"])
    if not (verify_success and f"-i {wan_iface} -j RETURN" in verify_output):
        success, msg = run_ebtables(["-A", chain_name, "-i", wan_iface, "-j", "RETURN"])
        if not success:
            logger.error(f"Error añadiendo regla entrada WAN: {msg}")
            return False
        logger.info(f"Regla {chain_name} -i {wan_iface} -j RETURN añadida")
    
    # Regla 2: Permitir tráfico SALIDA hacia WAN
    if not (verify_success and f"-o {wan_iface} -j RETURN" in verify_output):
        success, msg = run_ebtables(["-A", chain_name, "-o", wan_iface, "-j", "RETURN"])
        if not success:
            logger.error(f"Error añadiendo regla salida WAN: {msg}")
            return False
        logger.info(f"Regla {chain_name} -o {wan_iface} -j RETURN añadida")
    
    # Regla 3: DROP explícito para todo lo demás (bloqueo entre VLANs)
    # Insertar en posición 3 para asegurar orden correcto
    verify_success, verify_output = run_ebtables(["-L", chain_name, "--Ln"])
    # Contar líneas de reglas existentes (excluyendo header)
    if verify_success:
        pass
    
    # Verificar si ya existe una regla DROP
    drop_exists = verify_success and "-j DROP" in verify_output
    
    if not drop_exists:
        # LOG before DROP (Full Logging)
        run_ebtables(["-A", chain_name, "--log-level", "info", "--log-prefix", f"[JSB-EBT-BLOCK] VLAN-{vlan_id} ISO ", "-j", "CONTINUE"])
        success, msg = run_ebtables(["-A", chain_name, "-j", "DROP"])
        
        if not success:
            logger.error(f"Error añadiendo regla DROP en {chain_name}: {msg}")
            return False
        logger.info(f"Regla {chain_name} -j DROP añadida con LOG")
    
    # Agregar reglas en FORWARD que redireccionen cada interfaz VLAN a esta cadena
    for i, phys_iface in enumerate(vlan_interfaces, start=1):
        if not add_vlan_interface_to_forward(vlan_id, phys_iface):
            logger.error(f"Error agregando regla FORWARD para interfaz {phys_iface}")
            return False
    
    logger.info(f"Aislamiento aplicado a VLAN {vlan_id} - Reglas WAN creadas")
    return True


def remove_isolation(vlan_id: Any, vlan_interfaces: List[str] = None) -> bool:
    """Remover aislamiento de una VLAN o Wi-Fi."""
    chain_name = f"FORWARD_VLAN_{vlan_id}" if str(vlan_id).isdigit() else f"FORWARD_{str(vlan_id).upper()}"
    
    # Eliminar reglas en FORWARD que redireccionan a esta cadena
    if vlan_interfaces:
        for iface in vlan_interfaces:
            # Verificar y eliminar regla de redirección en FORWARD
            success, output = run_ebtables(["-L", "FORWARD", "--Ln"])
            if success and f"-i {iface} -j {chain_name}" in output:
                success, msg = run_ebtables(["-D", "FORWARD", "-i", iface, "-j", chain_name])
                if success:
                    logger.info(f"Regla FORWARD -i {iface} -j {chain_name} eliminada")
                else:
                    logger.error(f"Error eliminando regla FORWARD para {iface}: {msg}")
    
    # Siempre intentar hacer flush de la cadena (elimina todas las reglas dentro, incluyendo DROP)
    logger.info(f"Eliminando todas las reglas de {chain_name} (incluye WAN ACCEPT y DROP)...")
    success, msg = run_ebtables(["-F", chain_name])
    
    if success:
        logger.info(f"Reglas de {chain_name} eliminadas correctamente")
    else:
        # Si falla, podría ser porque la cadena no existe, que es ok
        if "Table does not exist" in msg or "No such file" in msg or "does not exist" in msg:
            logger.info(f"Cadena {chain_name} no existe (ya fue eliminada o nunca se creó)")
        else:
            logger.error(f"Error al hacer flush de {chain_name}: {msg}")
            return False
    
    logger.info(f"Aislamiento removido de VLAN {vlan_id}")
    return True


# =============================================================================
# UTILIDADES PARA MAC WHITELIST
# =============================================================================

def validate_mac_address(mac: str) -> bool:
    """Validar que una dirección MAC tenga formato XX:XX:XX:XX:XX:XX."""
    if not isinstance(mac, str):
        return False
    
    # Validar formato XX:XX:XX:XX:XX:XX
    pattern = r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
    if not re.match(pattern, mac):
        return False
    
    # Validación pasó
    return True


def normalize_mac_address(mac: str) -> str:
    """Normalizar y sanitizar MAC a formato estándar XX:XX:XX:XX:XX:XX en mayúsculas.
    
    Args:
        mac: Dirección MAC a normalizar (puede contener : o - como separador)
    
    Returns:
        MAC normalizada en formato XX:XX:XX:XX:XX:XX
        
    Note:
        Esta función sanitiza la entrada eliminando caracteres no hexadecimales
        excepto los separadores : y -
    """
    if not isinstance(mac, str):
        return ""
    
    # Sanitizar: eliminar cualquier carácter que no sea hexadecimal, ':', o '-'
    sanitized = ''.join(c for c in mac if c in '0123456789ABCDEFabcdef:-')
    
    # Normalizar: convertir a mayúsculas y usar ':' como separador
    normalized = sanitized.upper().replace('-', ':')
    
    return normalized


def apply_mac_whitelist_rules(_, __, ___) -> bool:
    """Aplicar reglas de ebtables para MAC whitelist en VLAN 1.
    
    Cuando whitelist está habilitada:
    - Solo MACs en la whitelist pueden comunicarse
    - Resto son bloqueadas
    - Se asegura que el tráfico pase por FORWARD_VLAN_1
    
    Usa ebtables con:
    - FORWARD: redirige tráfico de interfaces VLAN 1 a FORWARD_VLAN_1
    - FORWARD_VLAN_1: protege tráfico entre VLANs
    
      -j DROP                                   (rechaza MACs no whitelisted)
    """

def apply_mac_filter_rules(vlan_id: Any, _, blacklist: list) -> bool:
    """Aplicar reglas de MAC blacklist para una VLAN o Wi-Fi.
    
    Bloquea las MACs en la lista. El resto sigue su curso (aislado o no).
    """
    if vlan_id == "wifi":
        chain_name = "FORWARD_WIFI"
    else:
        chain_name = f"FORWARD_VLAN_{vlan_id}"
    
    logger.info(f"Aplicando MAC blacklist a {vlan_id} (cadena: {chain_name})")
    
    # Validar que las MACs sean válidas
    for mac in blacklist:
        if not validate_mac_address(mac):
            logger.error(f"MAC inválida en blacklist: {mac}")
            return False
    
    # PASO 1: Asegurar que la cadena existe
    if not create_vlan_chain(vlan_id):
        logger.error(f"No se pudo crear cadena {chain_name}")
        return False
    
    # PASO 2: Obtener interfaces y redirigir tráfico
    vlans_cfg = load_vlans_config()
    tagging_cfg = load_tagging_config()
    vlan_iface_map = build_vlan_interface_map(vlans_cfg.get("vlans", []), tagging_cfg)
    
    if vlan_id == "wifi":
        wifi_cfg = load_wifi_config()
        vlan_interfaces = [wifi_cfg.get("interface")] if wifi_cfg.get("interface") else []
    else:
        vlan_interfaces = vlan_iface_map.get(vlan_id, [])
    
    if vlan_interfaces:
        for vlan_iface in vlan_interfaces:
            # Asegurar redirección en FORWARD
            add_vlan_interface_to_forward(vlan_id, vlan_iface)
    
    # PASO 3: Limpiar reglas de MAC filter anteriores
    # Buscamos reglas con -s <mac> -j DROP o -d <mac> -j DROP
    success, output = run_ebtables(["-L", chain_name, "--Ln"])
    if success:
        lines = output.strip().split('\n')
        # Limpiar de atrás hacia adelante para no alterar índices durante el borrado
        for line in reversed(lines):
            if (('-s ' in line) or ('-d ' in line)) and ('-j DROP' in line):
                # Solo borrar si NO es el DROP final de aislamiento (el final no tiene MAC)
                if any(m in line for m in [':']) or '-s' in line or '-d' in line:
                   # Extraer parámetros para borrar de forma precisa
                   parts = line.split()
                   try:
                       if '-s' in parts:
                           mac = parts[parts.index('-s') + 1]
                           run_ebtables(["-D", chain_name, "-s", mac, "-j", "DROP"])
                       elif '-d' in parts:
                           mac = parts[parts.index('-d') + 1]
                           run_ebtables(["-D", chain_name, "-d", mac, "-j", "DROP"])
                   except: continue

    # PASO 4: Aplicar reglas de Blacklist (al principio de la cadena)
    if blacklist:
        for mac_addr in blacklist:
            normalized_mac = normalize_mac_address(mac_addr)
            # LOG before DROP
            run_ebtables(["-A", chain_name, "-s", normalized_mac, "--log-prefix", f"[JSB-EBT-BLOCK] {vlan_id} MAC-S ", "-j", "CONTINUE"])
            run_ebtables(["-A", chain_name, "-s", normalized_mac, "-j", "DROP"])
            
            run_ebtables(["-A", chain_name, "-d", normalized_mac, "--log-prefix", f"[JSB-EBT-BLOCK] {vlan_id} MAC-D ", "-j", "CONTINUE"])
            run_ebtables(["-A", chain_name, "-d", normalized_mac, "-j", "DROP"])
    
    logger.info(f"MAC blacklist aplicada a {vlan_id} con {len(blacklist)} entradas")
    return True


def remove_mac_filter_rules(vlan_id: Any) -> bool:
    """Remover todas las reglas de MAC blacklist de las cadenas ebtables.
    
    Elimina las reglas -s <mac> -j DROP y -d <mac> -j DROP.
    """
    if vlan_id == "wifi":
        chain_name = "FORWARD_WIFI"
    else:
        chain_name = f"FORWARD_VLAN_{vlan_id}"
    
    # Verificar si está aislada
    ebtables_cfg = load_ebtables_config()
    is_isolated = False
    if vlan_id == "wifi":
        is_isolated = ebtables_cfg.get("wifi", {}).get("isolated", False)
    else:
        is_isolated = ebtables_cfg.get("vlans", {}).get(str(vlan_id), {}).get("isolated", False)
    
    # Limpiar reglas de blacklist de la cadena
    success, output = run_ebtables(["-L", chain_name, "--Ln"])
    if success:
        lines = output.strip().split('\n')
        for line in reversed(lines):
            if ('-s ' in line or '-d ' in line) and ('-j DROP' in line):
                parts = line.split()
                try:
                    if '-s' in parts:
                        mac = parts[parts.index('-s') + 1]
                        run_ebtables(["-D", chain_name, "-s", mac, "-j", "DROP"])
                    elif '-d' in parts:
                        mac = parts[parts.index('-d') + 1]
                        run_ebtables(["-D", chain_name, "-d", mac, "-j", "DROP"])
                except: continue
    
    # Si NO está aislada, podemos eliminar la redirección en FORWARD si ya no hay filtros
    if not is_isolated:
        if vlan_id == "wifi":
            wifi_cfg = load_wifi_config()
            vlan_interfaces = [wifi_cfg.get("interface")] if wifi_cfg.get("interface") else []
        else:
            vlans_cfg = load_vlans_config()
            tagging_cfg = load_tagging_config()
            vlan_iface_map = build_vlan_interface_map(vlans_cfg.get("vlans", []), tagging_cfg)
            vlan_interfaces = vlan_iface_map.get(vlan_id, [])
        
        for vlan_iface in vlan_interfaces:
            remove_vlan_interface_from_forward(vlan_iface)
    
    logger.info(f"MAC blacklist removida de {vlan_id}")
    return True
