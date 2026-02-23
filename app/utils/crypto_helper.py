"""
Módulo de utilidades criptográficas para JSBach V4.4.
Proporciona:
- Cifrado simétrico autenticado (ChaCha20-Poly1305) para secretos de switches.
- Hashing de contraseñas (Argon2) para usuarios de la CLI/Web.
"""

import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# --- ChaCha20-Poly1305 (Symmetric Encryption) ---

def encrypt_string(plain_text: str, key_b64: str) -> str:
    """
    Cifra una cadena usando ChaCha20-Poly1305.
    Retorna: base64(nonce + ciphertext)
    """
    try:
        key = base64.b64decode(key_b64)
        chacha = ChaCha20Poly1305(key)
        nonce = os.urandom(12)
        ciphertext = chacha.encrypt(nonce, plain_text.encode('utf-8'), None)
        # El tag está incluido al final del ciphertext por la librería cryptography
        return base64.b64encode(nonce + ciphertext).decode('utf-8')
    except Exception as e:
        raise ValueError(f"Error en el cifrado: {e}")

def decrypt_string(encrypted_text_b64: str, key_b64: str) -> str:
    """
    Descifra una cadena usando ChaCha20-Poly1305.
    """
    try:
        key = base64.b64decode(key_b64)
        data = base64.b64decode(encrypted_text_b64)
        nonce = data[:12]
        ciphertext = data[12:]
        chacha = ChaCha20Poly1305(key)
        decrypted = chacha.decrypt(nonce, ciphertext, None)
        return decrypted.decode('utf-8')
    except Exception as e:
        raise ValueError(f"Error en el descifrado (posible llave incorrecta): {e}")

# --- Argon2 (Password Hashing) ---

ph = PasswordHasher()

def hash_password(password: str) -> str:
    """
    Genera un hash Argon2 para una contraseña.
    """
    return ph.hash(password)

def verify_password(password_hash: str, password: str) -> bool:
    """
    Verifica una contraseña contra un hash Argon2.
    """
    try:
        return ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False

# --- Master Key Helper ---

def generate_master_key() -> str:
    """
    Genera una nueva llave de 256 bits codificada en Base64.
    """
    return base64.b64encode(os.urandom(32)).decode('utf-8')

def get_master_key() -> str:
    """
    Carga la llave maestra desde config/secrets.env.
    """
    # Intentar encontrar la raíz del proyecto (asumiendo que estamos en app/utils o similar)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
    secrets_file = os.path.join(project_root, 'config', 'secrets.env')
    
    if os.path.exists(secrets_file):
        try:
            with open(secrets_file, 'r') as f:
                for line in f:
                    if line.startswith('JSBACH_CRYPTO_KEY='):
                        return line.split('=', 1)[1].strip()
        except Exception:
            pass
    return None
