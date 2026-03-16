"""
Módulo de ayuda para MFA (Multi-Factor Authentication) usando TOTP.
Basado en la librería pyotp.
"""

import pyotp
import qrcode
import io
import base64
from typing import Tuple, Optional
from app.utils import crypto_helper

def generate_mfa_secret() -> str:
    """Genera un nuevo secreto base32 para TOTP."""
    return pyotp.random_base32()

def get_totp_uri(username: str, secret: str, issuer_name: str = "JSBach") -> str:
    """Genera la URI para configurar aplicaciones de autenticación."""
    return pyotp.totp.TOTP(secret).provisioning_uri(name=username, issuer_name=issuer_name)

def verify_totp_code(secret: str, code: str) -> bool:
    """Verifica si un código TOTP es válido para el secreto dado."""
    if not code or not secret:
        return False
    totp = pyotp.TOTP(secret)
    return totp.verify(code)

def generate_qr_base64(uri: str) -> str:
    """Genera un código QR en formato base64 a partir de una URI."""
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(uri)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()
