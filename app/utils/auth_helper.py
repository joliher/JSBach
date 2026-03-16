"""
Funciones auxiliares de autenticación para JSBach V4.7
Usadas tanto por el login web como por la autenticación de la CLI
"""

import json
import os
import hashlib
from typing import Optional, Tuple
from datetime import datetime
from app.utils import crypto_helper, mfa_helper

def hash_password(password: str) -> str:
    """
    Hashea una contraseña usando Argon2.
    """
    return crypto_helper.hash_password(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica una contraseña. Soporta tanto Argon2 como el legado SHA256 para permitir migración.
    """
    if hashed_password.startswith("$argon2"):
        return crypto_helper.verify_password(hashed_password, plain_password)
    elif hashed_password.startswith("sha256:"):
        # Verificación legacy
        legacy_hash = hashed_password.split(":", 1)[1]
        return hashlib.sha256(plain_password.encode('utf-8')).hexdigest() == legacy_hash
    return False

def load_users(config_path: str) -> dict:
    """
    Carga usuarios desde un archivo de configuración JSON.
    Args:
        config_path: Ruta al archivo JSON de configuración
    Returns:
        Diccionario con los usuarios
    """
    if not os.path.exists(config_path):
        return {"users": []}
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def authenticate_user(username: str, password: str, config_path: str) -> Tuple[bool, Optional[dict]]:
    """
    Autentica un usuario contra el archivo de configuración.
    Args:
        username: Usuario
        password: Contraseña
        config_path: Ruta al archivo de configuración
    Returns:
        (True, user_data) si autenticado, (False, None) en caso contrario
    """
    data = load_users(config_path)
    users = data.get("users", [])
    
    for user in users:
        if user["username"] == username and user.get("enabled", True):
            if verify_password(password, user["password_hash"]):
                return True, user
    return False, None

def verify_mfa_code(username: str, code: str, config_path: str) -> bool:
    """
    Verifica el código MFA para un usuario.
    """
    data = load_users(config_path)
    for user in data.get("users", []):
        if user["username"] == username:
            if not user.get("mfa_enabled"):
                return True
            secret = user.get("mfa_secret")
            return mfa_helper.verify_totp_code(secret, code)
    return False

def save_mfa_secret(username: str, secret: str, enabled: bool, config_path: str) -> bool:
    """
    Guarda el secreto MFA y activa el flag.
    """
    data = load_users(config_path)
    found = False
    for user in data.get("users", []):
        if user["username"] == username:
            user["mfa_secret"] = secret
            user["mfa_enabled"] = enabled
            found = True
            break
    
    if found:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        return True
    return False

def create_user(username: str, password: str, role: str = "admin") -> dict:
    """
    Crea un nuevo diccionario de usuario.
    Args:
        username: Usuario
        password: Contraseña
        role: Rol del usuario
    Returns:
        Diccionario de usuario
    """
    return {
        "username": username,
        "password_hash": hash_password(password),
        "role": role,
        "created_at": datetime.now().isoformat(),
        "enabled": True,
        "mfa_enabled": False,
        "mfa_secret": None
    }
