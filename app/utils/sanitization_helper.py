"""
Módulo de sanitización para JSBach V4.7.
Proporciona utilidades para escapar caracteres especiales de Tcl/Expect
y filtrar comandos CLI potencialmente peligrosos.
"""

import re

def sanitize_expect_input(value: str) -> str:
    """
    Escapa caracteres especiales de Tcl para evitar ejecuciones accidentales
    dentro de un entorno Expect.
    Caracteres escapados: [ ] $ \ { } "
    """
    if not isinstance(value, str):
        return str(value)
    
    # Escapar la barra invertida primero para evitar doble escape
    # Luego escapar otros caracteres especiales de Tcl/Expect
    specials = {
        '\\': '\\\\',
        '[': '\\[',
        ']': '\]',
        '$': '\$',
        '{': '\{',
        '}': '\}',
        '"': '\\"',
    }
    
    for char, replacement in specials.items():
        value = value.replace(char, replacement)
        
    return value

def sanitize_cli_command(command: str) -> str:
    """
    Sanitiza un comando CLI para evitar inyección de comandos encadenados.
    Elimina caracteres de control de shell y redirección.
    """
    if not isinstance(command, str):
        return str(command)
    
    # Bloquear caracteres de control y redirección de shell comunes
    # ; & | ` > < ! ( )
    # Mantenemos las comillas y espacios si son necesarios, pero limitamos el daño
    return re.sub(r"[;&|`><!()]", "", command).strip()

def sanitize_ip_or_host(value: str) -> str:
    """
    Sanitiza estrictamente una IP o nombre de host.
    Solo permite caracteres alfanuméricos, puntos y guiones.
    """
    if not isinstance(value, str):
        return str(value)
    return re.sub(r"[^a-zA-Z0-9.-]", "", value).strip()
