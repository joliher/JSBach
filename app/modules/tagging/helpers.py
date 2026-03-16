# app/core/helpers/helper_tagging.py
"""Helper functions para el módulo Tagging."""

import os
from ...utils.global_helpers import run_command


def run_cmd(cmd, ignore_error=False):
    """Execute command and return (success: bool, output: str).
    
    Args:
        cmd: Lista de comandos a ejecutar
        ignore_error: Si True, no reporta error
    
    Returns:
        (success: bool, output: str)
    """
    success, output = run_command(cmd)
    return success, output


def bridge_exists() -> bool:
    """Verificar si el bridge br0 existe.
    
    Returns:
        True si existe, False en caso contrario
    """
    return os.path.exists("/sys/class/net/br0")


def parse_vlan_range(vlan_string: str) -> list:
    """Parsea una sintaxis de VLAN con rangos como '1,2,3-10,12,14-15'.
    
    Soporta:
    - Valores individuales: 1,2,3
    - Rangos: 3-10 (expande a 3,4,5,6,7,8,9,10)
    - Combinaciones: 1,2,3-10,12,14-15
    - Orden arbitrario: 10-3,1,2 es igual a 1,2,3-10
    
    NO soporta espacios después de comas o en rangos:
    - ❌ '3-10, 12' (espacio después de coma)
    - ❌ '3 - 10' (espacios alrededor del guion)
    
    Args:
        vlan_string: String con sintaxis de VLANs
    
    Retorna:
        lista ordenada y sin duplicados de VLANs como strings, o [] si es inválido
    """
    if not vlan_string or not isinstance(vlan_string, str):
        return []
    
    # Validar que NO haya espacios después de comas o alrededor de guiones
    # Formato válido: 1,2,3-10,12,14-15
    if ' ' in vlan_string:
        return []  # Inválido si hay espacios
    
    vlan_set = set()
    
    # Dividir por comas
    parts = vlan_string.split(",")
    
    for part in parts:
        if not part:  # Parte vacía
            return []
        
        # Verificar si es un rango (contiene guion)
        if "-" in part:
            range_parts = part.split("-")
            if len(range_parts) == 2:
                try:
                    start = int(range_parts[0])
                    end = int(range_parts[1])
                    # Validar rango de VLAN (1-4094)
                    if start < 1 or start > 4094 or end < 1 or end > 4094:
                        return []
                    # Soportar rangos en ambas direcciones
                    if start > end:
                        start, end = end, start
                    for vid in range(start, end + 1):
                        vlan_set.add(str(vid))
                except (ValueError, TypeError):
                    return []
            else:
                return []  # Rango con más de un guion es inválido
        else:
            # Valor individual
            try:
                vid = int(part)
                if 1 <= vid <= 4094:
                    vlan_set.add(str(vid))
                else:
                    return []  # VLAN fuera de rango
            except (ValueError, TypeError):
                return []
    
    # Retornar ordenado
    return sorted(list(vlan_set), key=int)



