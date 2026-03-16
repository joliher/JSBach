def create_cli_systemd_service(target_path, venv_path):
    info("Creando servicio systemd para CLI")
    cli_path = os.path.join(target_path, "cli_server.py")
    service_content = f"""[Unit]
Description=JSBach CLI Service
BindsTo=jsbach.service
PartOf=jsbach.service
After=jsbach.service

[Service]
Type=simple
User=jsbach
Group=jsbach
UMask=0027
WorkingDirectory={target_path}
Environment=\"PATH={venv_path}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\"
ExecStart={venv_path}/bin/python3 {cli_path}
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
    service_path = "/etc/systemd/system/jsbach-cli.service"
    with open(service_path, "w") as f:
        f.write(service_content)

    cmds = [
        "systemctl daemon-reload",
        "systemctl enable jsbach-cli",
        "systemctl restart jsbach-cli"
    ]
    for c in cmds:
        result = subprocess.run(c, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            error(f"Fallo al ejecutar: {c}\n{result.stderr.strip()}")
    success("Servicio systemd CLI creado y en ejecución")
#!/usr/bin/env python3

import os
import shutil
import subprocess
import sys
import platform
import getpass
import json
import hashlib
from datetime import datetime

###############
#   Colores   #
###############
BLUE = "\033[94m"
YELLOW = "\033[93m"
RED = "\033[91m"
GREEN = "\033[92m"
RESET = "\033[0m"

###############
#   Mensajes  #
###############
def info(msg):
    print(f"{BLUE}[INFO]{RESET} {msg}")

def warn(msg):
    print(f"{YELLOW}[WARN]{RESET} {msg}")

def error(msg, exit_code=1):
    print(f"{RED}[ERROR]{RESET} {msg}")
    sys.exit(exit_code)

def success(msg):
    print(f"{GREEN}[OK]{RESET} {msg}")

def cmd(msg):
    print(f"{BLUE}[CMD]{RESET} {msg}")

############
#   Logs  #
############
def create_logs_directory(target_path):
    log_dir = os.path.join(target_path, "logs")
    if not os.path.exists(log_dir):
        info(f"Creando directorio de logs en {log_dir}")
        os.makedirs(log_dir)

    # 750: jsbach rw+x, grupo r-x, otros sin acceso
    info(f"Cambiando permisos de {log_dir} a 750 y propietario a jsbach:jsbach")
    subprocess.run(f"chown jsbach:jsbach {log_dir}", shell=True)
    subprocess.run(f"chmod 750 {log_dir}", shell=True)
    success(f"Directorio de logs creado y permisos establecidos en {log_dir}")

############
#  Config  #
############
def create_config_directory(target_path):
    config_dir = os.path.join(target_path, "config")
    if not os.path.exists(config_dir):
        info(f"Creando directorio de config en {config_dir}")
        os.makedirs(config_dir)

    # 700: acceso exclusivo para jsbach, otros sin acceso
    info(f"Cambiando permisos de {config_dir} a 700 y propietario a jsbach:jsbach")
    subprocess.run(f"chown jsbach:jsbach {config_dir}", shell=True)
    subprocess.run(f"chmod 700 {config_dir}", shell=True)
    success(f"Directorio de config creado y permisos establecidos en {config_dir}")

    # Copiar perfiles de Expect si existen
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    src_profiles = os.path.join(base_dir, "config", "expect", "profiles")
    dst_profiles = os.path.join(config_dir, "expect", "profiles")

    if os.path.exists(src_profiles):
        info(f"Copiando perfiles de Expect desde {src_profiles}")
        if not os.path.exists(dst_profiles):
            os.makedirs(dst_profiles)
        
        # Copiar archivos JSON
        for item in os.listdir(src_profiles):
            s = os.path.join(src_profiles, item)
            d = os.path.join(dst_profiles, item)
            if os.path.isfile(s):
                if os.path.abspath(s) == os.path.abspath(d):
                    continue
                shutil.copy2(s, d)
        
        # Establecer permisos restrictivos para perfiles (jsbach:jsbach 700 para dirs, 600 para archivos)
        subprocess.run(f"chown -R jsbach:jsbach {os.path.join(config_dir, 'expect')}", shell=True)
        subprocess.run(f"chmod -R 700 {os.path.join(config_dir, 'expect')}", shell=True)
        subprocess.run(f"find {dst_profiles} -type f -exec chmod 600 {{}} \\;", shell=True)
        success("Perfiles de Expect copiados correctamente")

        # Generar secrets.env
    secrets_file = os.path.join(config_dir, "secrets.env")
    if not os.path.exists(secrets_file):
        info(f"Generando llaves secretas en {secrets_file}")
        import secrets
        import base64
        secret_key = secrets.token_urlsafe(32)
        crypto_key = base64.b64encode(os.urandom(32)).decode('utf-8')
        with open(secrets_file, "w") as f:
            f.write(f"JSBACH_SECRET_KEY={secret_key}\n")
            f.write(f"JSBACH_CRYPTO_KEY={crypto_key}\n")
        
        # Permisos estrictos para el archivo de secretos (solo root/jsbach lectura)
        subprocess.run(f"chown jsbach:jsbach {secrets_file}", shell=True)
        subprocess.run(f"chmod 600 {secrets_file}", shell=True)
        success("Llaves secretas generadas correctamente")

###############
#   QOL       #
###############
def ask(question, default=None):
    if default is not None:
        q = f"{question} [{default}]: "
    else:
        q = f"{question}: "
    answer = input(q).strip()
    return answer if answer else default

def ask_yes_no(question, default="s"):
    default = default.lower()
    if default not in ("s","n"):
        raise ValueError("default debe ser 's' o 'n'")
    prompt = f"{question} [{'S/n' if default=='s' else 's/N'}]: "
    while True:
        answer = input(prompt).strip().lower()
        if answer == "":
            return default
        if answer in ("s","n"):
            return answer

def ensure_root():
    if os.geteuid() != 0:
        error("Debes ejecutar este script como root.")

###############
#   Dependencias
###############
def install_dependencies():
    info("Instalando dependencias del sistema...")
    
    # Paquetes necesarios:
    # - python3, python3-pip, python3-venv: entorno Python
    # - iptables: reglas de firewall, NAT, DMZ
    # - iproute2: comandos ip y bridge para VLANs y routing
    # - expect: orquestación de periféricos remotos
    # - netcat-openbsd: conexión por red (nc)
    commands = [
        "apt update -qq",
        "apt install -y python3 python3-pip python3-venv iptables iproute2 ebtables expect netcat-openbsd hostapd iw conntrack dnsmasq dhcpcd procps -qq"
    ]
    for c in commands:
        cmd(c)
        result = subprocess.run(c, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            error(f"Falló el comando: {c}\n{result.stderr.strip()}")

###############
#   Usuarios
###############
def create_user(username="jsbach"):
    try:
        # Comprobar si el usuario existe
        subprocess.run(f"id -u {username}", shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        info(f"Usuario {username} ya existe")
    except subprocess.CalledProcessError:
        info(f"Creando usuario {username}")
        result = subprocess.run(f"useradd -m -s /bin/bash {username}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            error(f"No se pudo crear el usuario {username}: {result.stderr.strip()}")
        success(f"Usuario {username} creado correctamente")

###############
#   Proyecto
###############
DIRECTORY_WHITELIST = ["app", "web", "scripts"]  # directorios de código fuente
FILE_WHITELIST = ["main.py", "cli_server.py"]  # archivos raíz necesarios

def prepare_directory(target_path):
    info(f"Preparando directorio del proyecto en {target_path}")
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    if not os.path.exists(target_path):
        info(f"Creando directorio {target_path}")
        os.makedirs(target_path)

    # Copiar directorios de código fuente
    for folder in DIRECTORY_WHITELIST:
        src = os.path.join(BASE_DIR, folder)
        dst = os.path.join(target_path, folder)
        if os.path.exists(src) and not os.path.exists(dst):
            info(f"Copiando {folder}/ ...")
            shutil.copytree(src, dst)
        else:
            if not os.path.exists(dst):
                warn(f"No existe carpeta {folder}/ para copiar")
    
    # Copiar archivos raíz necesarios
    for file in FILE_WHITELIST:
        src = os.path.join(BASE_DIR, file)
        dst = os.path.join(target_path, file)
        if os.path.exists(src) and not os.path.exists(dst):
            info(f"Copiando {file} ...")
            shutil.copy2(src, dst)
        elif not os.path.exists(src):
            warn(f"No existe archivo {file} para copiar")

###############
#   Entorno virtual
###############
def create_venv(target_path):
    info("Creando entorno virtual Python")
    venv_path = os.path.join(target_path, "venv")
    if os.path.exists(venv_path):
        info("Entorno virtual ya existe")
        return venv_path
    result = subprocess.run(f"python3 -m venv {venv_path}", shell=True,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        error(f"Fallo al crear el entorno virtual: {result.stderr.strip()}")
    # Instalar paquetes
    result = subprocess.run(f"{venv_path}/bin/pip install fastapi[all] uvicorn requests cryptography argon2-cffi pyotp slowapi qrcode pillow", shell=True,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        error(f"Fallo al instalar paquetes en el entorno virtual: {result.stderr.strip()}")
    success("Entorno virtual configurado correctamente")
    return venv_path

###############
#   Servicio systemd
###############
def set_directory_permissions(target_path):
    """Establecer permisos con mínimos privilegios. Otros (o=0) en todo el proyecto."""
    info("Configurando permisos de directorios y archivos (principio de mínimo privilegio)")

    # --- 1. Propietario: jsbach:jsbach en todo el árbol ---
    subprocess.run(f"chown -R jsbach:jsbach {target_path}", shell=True)

    # --- 2. Directorio raíz del proyecto ---
    # 750: jsbach entra, grupo puede listar, otros nada
    subprocess.run(f"chmod 750 {target_path}", shell=True)

    # --- 3. app/ y subdirectorios Python ---
    app_dir = os.path.join(target_path, "app")
    if os.path.exists(app_dir):
        # Directorios: 550 (r-xr-x---)
        subprocess.run(f"find {app_dir} -type d -exec chmod 550 {{}} \\;", shell=True)
        # Archivos .py: 440 (r--r-----) — solo lectura, jsbach no necesita escribirlos
        subprocess.run(f"find {app_dir} -type f -name '*.py' -exec chmod 440 {{}} \\;", shell=True)
        # Archivos .md de ayuda CLI: solo lectura
        subprocess.run(f"find {app_dir} -type f -name '*.md' -exec chmod 440 {{}} \\;", shell=True)

        # Scripts Expect: jsbach necesita leerlos para pasarlos a /usr/bin/expect
        # 500 directorio (r-x------), 400 archivos (r--------)
        expect_scripts = os.path.join(app_dir, "modules", "expect", "scripts")
        if os.path.exists(expect_scripts):
            info(f"  Expect scripts: 500/400 (solo jsbach puede leer/ejecutar)")
            subprocess.run(f"chmod 500 {expect_scripts}", shell=True)
            subprocess.run(f"find {expect_scripts} -type f -exec chmod 400 {{}} \\;", shell=True)

    # --- 4. web/ --- solo lectura para jsbach (FastAPI sirve estáticos)
    web_dir = os.path.join(target_path, "web")
    if os.path.exists(web_dir):
        info(f"  Web: 550/440 — solo lectura")
        subprocess.run(f"find {web_dir} -type d -exec chmod 550 {{}} \\;", shell=True)
        subprocess.run(f"find {web_dir} -type f -exec chmod 440 {{}} \\;", shell=True)

    # --- 5. config/ --- acceso exclusivo jsbach (rw sin grupo)
    config_dir = os.path.join(target_path, "config")
    if os.path.exists(config_dir):
        info(f"  Config: 700/600 — acceso exclusivo jsbach")
        subprocess.run(f"find {config_dir} -type d -exec chmod 700 {{}} \\;", shell=True)
        subprocess.run(f"find {config_dir} -type f -exec chmod 600 {{}} \\;", shell=True)

    # --- 6. logs/ --- jsbach escribe; grupo solo lectura; otros nada
    logs_dir = os.path.join(target_path, "logs")
    if os.path.exists(logs_dir):
        info(f"  Logs: 750/640 — jsbach escribe, grupo lee")
        subprocess.run(f"chmod 750 {logs_dir}", shell=True)
        subprocess.run(f"find {logs_dir} -type f -exec chmod 640 {{}} \\;", shell=True)

    # --- 7. scripts/ --- solo lectura (instalador/tests)
    scripts_dir = os.path.join(target_path, "scripts")
    if os.path.exists(scripts_dir):
        info(f"  Scripts: 550/440 — solo lectura")
        subprocess.run(f"find {scripts_dir} -type d -exec chmod 550 {{}} \\;", shell=True)
        subprocess.run(f"find {scripts_dir} -type f -exec chmod 440 {{}} \\;", shell=True)

    # --- 8. Archivos raíz ejecutables ---
    for f in ["main.py", "cli_server.py"]:
        fp = os.path.join(target_path, f)
        if os.path.exists(fp):
            subprocess.run(f"chmod 550 {fp}", shell=True)

    # --- 9. venv/ --- jsbach necesita ejecutar binarios, grupo puede leer ---
    venv_dir = os.path.join(target_path, "venv")
    if os.path.exists(venv_dir):
        info(f"  Venv: 750/640+550 — jsbach ejecuta, grupo lee")
        subprocess.run(f"find {venv_dir} -type d -exec chmod 750 {{}} \\;", shell=True)
        subprocess.run(f"find {venv_dir} -type f -exec chmod 640 {{}} \\;", shell=True)
        # Binarios del venv necesitan ser ejecutables
        subprocess.run(f"find {venv_dir}/bin -type f -exec chmod 750 {{}} \\;", shell=True)

    # --- 10. BARRIDO FINAL: garantizar o=0 en absolutamente todo ---
    info("  Barrido final: eliminando cualquier permiso residual para 'otros'...")
    subprocess.run(f"chmod -R o-rwx {target_path}", shell=True)

    success("Permisos configurados correctamente (o=0 garantizado en todo el proyecto)")

def create_systemd_service(target_path, venv_path, port):
    info("Creando servicio systemd")
    service_content = f"""[Unit]
Description=JSBach Web Service
After=network.target

[Service]
Type=simple
User=jsbach
Group=jsbach
UMask=0027
WorkingDirectory={target_path}
Environment="PATH={venv_path}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart={venv_path}/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port {port}
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
    service_path = "/etc/systemd/system/jsbach.service"
    with open(service_path, "w") as f:
        f.write(service_content)

    # Asegurar permisos correctos para el directorio del proyecto
    set_directory_permissions(target_path)

    cmds = ["systemctl daemon-reload",
            "systemctl enable jsbach",
            "systemctl restart jsbach"]
    for c in cmds:
        result = subprocess.run(c, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            error(f"Fallo al ejecutar: {c}\n{result.stderr.strip()}")
    success("Servicio systemd creado y en ejecución")


###############
#   Función para modificar sudoers
###############
def add_sudoers_entry(user, commands):
    sudoers_path = "/etc/sudoers.d/99_jsbach"

    # Asegurarnos de que el archivo sudoers existe y es seguro
    if not os.path.exists(sudoers_path):
        info(f"Creando archivo de sudoers para {user}")

    sudoers_entry = f"{user} ALL=(ALL) NOPASSWD: " + ", ".join(commands) + "\n"

    # Añadir al archivo sudoers
    with open(sudoers_path, "a") as f:
        f.write(sudoers_entry)

    success(f"Se ha añadido la entrada de sudoers para el usuario {user}")

###############
#   Crear archivo de autenticación
###############
def create_auth_file(target_path, username, password):
    """Crear archivo cli_users.json con el usuario inicial."""
    config_dir = os.path.join(target_path, "config")
    auth_file = os.path.join(config_dir, "cli_users.json")
    
    # Hash de la contraseña
    password_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
    
    # Estructura del usuario
    user_data = {
        "users": [
            {
                "username": username,
                "password_hash": f"sha256:{password_hash}",
                "role": "admin",
                "created_at": datetime.now().isoformat(),
                "enabled": True
            }
        ]
    }
    
    info(f"Creando archivo de autenticación en {auth_file}")
    try:
        with open(auth_file, 'w') as f:
            json.dump(user_data, f, indent=4)
        
        # Cambiar permisos y propietario
        subprocess.run(f"chown jsbach:jsbach {auth_file}", shell=True)
        subprocess.run(f"chmod 600 {auth_file}", shell=True)  # Solo lectura/escritura para el propietario
        
        success("Archivo de autenticación creado correctamente")
    except Exception as e:
        error(f"No se pudo crear el archivo de autenticación: {e}")

###############
#   MAIN
###############
if __name__ == "__main__":
    if platform.system() == "Windows":
        message = r"""
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣀⣀⣤⣤⣤⣤⠤⠤⠤⠤⢤⣤⣤⣤⣤⣀⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣴⠛⢉⡁⠀⠀⠀⢀⡀⠀⠀⠀⠐⠒⠁⠀⢴⡌⠻⣯⡙⠳⣶⡄⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⡾⠷⢋⠉⠀⠀⢀⣀⠁⠀⠀⠐⠀⠈⠹⣆⡀⢬⠻⣦⢹⣿⣧⡈⣿⡀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⠟⣀⡴⠛⠂⠀⠀⠃⠀⠀⠀⠀⠀⠀⠀⣄⠘⢷⡘⠀⠀⠘⣿⣟⠃⢸⣇⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣼⠏⠈⡁⠀⠀⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠃⠀⠻⠶⣄⡆⢨⣿⠳⣌⣿⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⣼⠁⠈⠁⠀⠀⠋⠁⠀⢠⠀⠀⠀⠀⠀⠀⠀⡄⠀⠀⠀⣤⠀⣛⠃⢀⣿⠀⣮⣿⡇⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣤⣇⣴⣼⣒⣶⣶⣶⣶⣴⣖⣀⣀⠀⠀⠀⠃⢠⡇⠀⠸⠃⠻⡄⠘⣷⢀⣸⣿⣇⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣶⣾⣧⣤⣤⣤⣠⠏⢠⠙⠘⣿⡿⣿⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⢻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠿⠟⠻⣿⡆⠘⢻⠿⣴⣦⣿⣟⣿⡆⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠟⠁⠀⠀⢀⣿⣇⢀⠀⣿⣱⣿⣷⠿⣿⡇⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣿⣿⠟⠉⣉⠉⠙⣿⣿⣿⠛⠉⠀⠀⠀⠀⠀⠀⠸⢧⣾⠀⣹⣿⣀⣿⡖⢺⣷⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⠏⠎⠉⠀⣀⠘⢁⡶⢰⣿⠀⠀⠷⠀⠀⠀⠀⠀⠀⠀⢀⣴⣿⢯⣝⣭⡍⢹⣇⢸⣿⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⢠⡟⢀⣴⠂⠀⢀⣴⡿⠁⣼⠃⠀⠀⢀⡠⠀⠀⢀⡀⢀⣼⡿⠀⠉⠀⠉⠀⠉⢸⣿⣿⣻⣇⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⣿⣵⠟⠁⢀⣼⣿⣿⠃⢰⠇⠀⢀⡰⠋⣠⡚⠂⠀⠀⠀⠛⠁⠀⠀⠀⠀⠀⢀⡈⢻⣟⢻⣿⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⣸⠟⠁⢀⣴⡯⠉⣸⡟⠀⢰⡏⠀⠈⠁⠀⠀⠀⠀⠤⠴⠀⠀⠀⠀⠀⠀⠀⠀⠈⢿⡄⢻⣧⣿⡇⠀⠀
⠀⠀⠀⠀⠀⢀⣴⠟⢀⡴⠛⢓⣤⠜⣿⠁⠀⠉⠃⡄⠀⠂⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢰⢰⣿⣧⣿⡙⢿⣷⠀⠀
⠀⠀⠀⢀⡴⠟⢁⡴⠛⠉⠉⠁⠀⠀⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⡀⠀⢀⠀⠀⠸⠛⢿⣿⠝⠃⠀⢿⡀⠀
⠀⢀⣼⡋⠀⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠃⠀⠀⠀⠀⠀⠹⠀⠀⠀⠀⠸⣿⡄⠀⠸⠿⣧⠀
⢠⣾⣿⣿⣷⣤⣤⣤⣄⣠⡄⠀⠀⠀⠀⠤⢀⣀⣼⠿⢆⣰⣶⠀⠀⠀⠀⠀⠀⠀⠀⣠⡶⠀⠀⠀⠀⠀⢸⣷⣆⠈⢧⣿⠀
⠀⠙⠻⠿⣿⣿⣿⣿⣿⣿⣿⣷⣶⣶⣶⣶⣶⣿⣷⣾⣽⣧⣇⠀⠀⢀⡀⠀⠀⠀⣼⠋⠿⠀⠀⠀⠀⠀⠀⠉⢻⣿⣀⣿⡄
⠀⠀⠀⠀⢀⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡟⠋⠉⠀⠀⠀⠀⠀⠀⠐⣾⡆⢠⣶⣿⣿⣿⣶⣶⣾⣿⣿⣿⣿⡇
⠀⠀⠀⠀⣼⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠿⠿⠋⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠼⠟⢁⣼⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇
⠀⠀⠀⣰⡿⠟⠛⠛⠛⠛⠋⠉⠋⠈⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠸⣿⡿⠿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇
⠀⠀⠀⣿⣿⣿⣶⣶⣶⣶⣶⣦⣤⣤⣤⣤⠀⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠐⠀⠀⠀⠀⠈⠃⠲⢢⣿⣿⣿⣿⣿⣿⣿⣿⡇
⠀⠀⠀⠹⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣶⣗⣶⠁⢀⣄⠀⠀⠂⠀⠀⠀⠀⠀⠀⠀⠀⠾⣿⣿⣿⣿⣿⣿⣿⣿⡇
⠀⠀⠀⠀⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⣿⣿⣶⠟⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢨⣽⣿⣿⣿⣿⣿⣿⡇
⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠿⠟⠉⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢈⣿⣿⣿⣿⣿⣿⡇
⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠟⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⣛⣿⣿⣿⣿⣿⣿⡇
⠀⠀⠀⠀⠀⣿⣿⣿⣿⣿⣿⣿⣿⡟⠁⠀⠀⠀⠀⠀⢀⡀⠀⠀⠀⠀⠀⠔⠃⠀⠀⠀⣀⣠⣤⣿⣿⣿⣿⣿⣿⣿⣿⡇
⠀⠀⠀⠀⠀⠻⣿⣿⣿⣿⣿⣿⣤⣤⣤⡀⠀⢀⣴⠞⠋⢀⣠⡀⠀⠀⠀⢰⣿⣶⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠀
⠀⠀⠀⠀⠀⠀⠙⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣾⣿⣷⣾⣶⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠁⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠉⠛⠻⠿⠿⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠿⠋⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣀⣀⠀⠀⠀⠀⠀⠈⠉⠉⠉⠙⠛⠛⠛⠛⠛⠛⠛⠛⠛⠛⠛⠛⠉⠁⣀⣀⠀⠀⠀⠀
"""
        print(message)
        sys.exit(1)

    ensure_root()
    info("Instalador JSBach")

    # Preguntar ruta de instalación
    target_path = ask("Ruta de instalación del proyecto", "/opt/JSBach")
    target_path = target_path.rstrip("/")

    if target_path == "/":
        warn("Has elegido '/' como ruta de instalación. Esto puede ser peligroso.")
        if ask_yes_no("Continuar?", "n") == "n":
            sys.exit(0)

    install_dependencies()
    create_user("jsbach")
    prepare_directory(target_path)
    create_logs_directory(target_path)
    create_config_directory(target_path)
    venv_path = create_venv(target_path)

    # Elegir puerto
    while True:
        port = ask("Puerto donde se ejecutará la web", "8100")
        if port not in ("80","8080","8000"):
            break
        warn("El puerto 80, 8080 y 8000 están ocupados. Escoge otro.")

    # Configurar credenciales de autenticación
    print()
    info("Configuración de credenciales de acceso")
    username = ask("Usuario para el sistema", "admin")
    password = ask("Contraseña", "")
    
    # Advertencia si la contraseña está vacía
    if not password:
        warn("⚠️ La contraseña está vacía. Esto es inseguro.")
        if ask_yes_no("¿Continuar sin contraseña?", "n") == "n":
            # Forzar que introduzca una contraseña
            while not password:
                password = ask("Contraseña (obligatoria)", "")
                if not password:
                    warn("Debe introducir una contraseña")
    
    print()

    create_systemd_service(target_path, venv_path, port)
    create_cli_systemd_service(target_path, venv_path)

    # --- CONFIGURACIÓN BASE INICIAL ---
    print()
    info("Configuración Base Inicial")
    default_iface = "eth0"
    try:
        import subprocess
        res = subprocess.run("ip -o link show | awk -F': ' '{print $2}'", shell=True, capture_output=True, text=True)
        ifaces = [i for i in res.stdout.split() if i not in ("lo", "br0") and not i.startswith("br0.")]
        if ifaces:
            default_iface = ifaces[0]
    except:
        pass
        
    physical_iface = ask("Interfaz física para gestión (VLAN 1 Untagged)", default_iface)
    
    # Generar archivos de config base
    config_dirs = [
        os.path.join(target_path, "config", "vlans"),
        os.path.join(target_path, "config", "tagging"),
        os.path.join(target_path, "config", "dhcp"),
        os.path.join(target_path, "config", "wifi"),
        os.path.join(target_path, "config", "nat"),
        os.path.join(target_path, "config", "dmz"),
        os.path.join(target_path, "logs", "dhcp"),
        os.path.join(target_path, "logs", "wifi"),
        os.path.join(target_path, "logs", "wan")
    ]
    for d in config_dirs:
        os.makedirs(d, exist_ok=True)
    
    vlans_cfg_dir = os.path.join(target_path, "config", "vlans")
    tagging_cfg_dir = os.path.join(target_path, "config", "tagging")
    
    with open(os.path.join(vlans_cfg_dir, "vlans.json"), "w") as f:
        import json
        json.dump({"status": 1, "vlans": [{"id": 1, "name": "Management", "ip_interface": "192.168.1.1/24", "dhcp_enabled": True}]}, f, indent=4)
        
    with open(os.path.join(tagging_cfg_dir, "tagging.json"), "w") as f:
        json.dump({"status": 1, "interfaces": [{"name": physical_iface, "vlan_untag": "1", "vlan_tag": ""}]}, f, indent=4)
        
    success(f"Configuración base creada: VLAN 1 Untagged en {physical_iface} (192.168.1.1/24)")

    # Definir los comandos permitidos en sudoers
    # Lista quirúrgica extraída del análisis del código fuente. Se permiten
    # banderas específicas (-A, -D, -F, etc.) pero se prohíbe la manipulación
    # arbitraria del binario.
    allowed_commands = [
        # --- IPTABLES ---
        "/usr/sbin/iptables -A *",
        "/usr/sbin/iptables -C *",
        "/usr/sbin/iptables -D *",
        "/usr/sbin/iptables -F *",
        "/usr/sbin/iptables -I *",
        "/usr/sbin/iptables -L *",
        "/usr/sbin/iptables -N *",
        "/usr/sbin/iptables -X *",
        "/usr/sbin/iptables -t nat *",
        "/usr/sbin/iptables -t mangle *",
        
        # --- EBTABLES ---
        "/usr/sbin/ebtables -A *",
        "/usr/sbin/ebtables -D *",
        "/usr/sbin/ebtables -F *",
        "/usr/sbin/ebtables -L *",
        "/usr/sbin/ebtables -N *",
        "/usr/sbin/ebtables -X *",
        "/usr/sbin/ebtables -t broute *",
        "/usr/sbin/ebtables -t nat *",
        "/usr/sbin/ebtables -t filter *",
        
        # --- NETWORK & IP ---
        "/usr/sbin/ip a *",
        "/usr/sbin/ip addr *",
        "/usr/sbin/ip addr flush *",
        "/usr/sbin/ip l *",
        "/usr/sbin/ip link *",
        "/usr/sbin/ip link add *",
        "/usr/sbin/ip link del *",
        "/usr/sbin/ip r *",
        "/usr/sbin/ip route *",
        "/usr/sbin/ip -4 *",
        "/usr/sbin/bridge vlan *",
        "/usr/sbin/bridge fdb *",
        
        # --- CONNTRACK ---
        "/usr/sbin/conntrack -D *",
        "/usr/sbin/conntrack -F",
        "/usr/sbin/conntrack -L *",
        
        # --- DHCP & DNS ---
        "/usr/sbin/dhcpcd -b *",
        "/usr/sbin/dhcpcd -k *",
        "/usr/sbin/dhcpcd -n *",
        "/usr/sbin/dhcpcd -x *",
        "/usr/sbin/dnsmasq * --log-facility=*",
        "/usr/sbin/dnsmasq --conf-file=*",
        "/usr/bin/resolvectl dns *",
        "/usr/bin/resolvectl revert *",
        
        # --- WIFI ---
        "/usr/sbin/hostapd -B *",
        "/usr/sbin/hostapd_cli -i *",
        
        # --- SYSTEM & SERVICES ---
        "/usr/sbin/sysctl -n *",
        "/usr/sbin/sysctl -w net.ipv4.ip_forward=*",
        "/usr/bin/ping -c *",
        "/usr/bin/stdbuf -oL *",
        "/usr/bin/pkill -F /opt/JSBach/config/dhcp/dnsmasq.pid",
        "/usr/bin/pkill -9 -F /opt/JSBach/config/dhcp/dnsmasq.pid",
        "/usr/bin/pkill -F /opt/JSBach/config/wifi/hostapd.pid",
        "/usr/bin/pkill -9 -F /opt/JSBach/config/wifi/hostapd.pid",
        
        # --- EXPECT (Strictly confined to modules) ---
        "/usr/bin/expect /opt/JSBach/app/modules/expect/scripts/*"
    ]

    # Añadir sudoers
    add_sudoers_entry("jsbach", allowed_commands)
    
    # Crear archivo de autenticación
    create_auth_file(target_path, username, password)

    success(f"Instalación completada. Accede a la web en http://localhost:{port}/\n")

    # Mostrar credenciales
    if password:
        info(f"Puede iniciar sesión con usuario '{username}' y contraseña '{password}'")
    else:
        info(f"Puede iniciar sesión con usuario '{username}' y contraseña vacía")
    
    print()
    info("Para administrar el servicio JSBach, usa los siguientes comandos:")
    print("  systemctl status jsbach      # Ver estado del servicio")
    print("  systemctl restart jsbach     # Reiniciar el servicio")
    print("  systemctl stop jsbach        # Detener el servicio")
    print("  systemctl start jsbach       # Iniciar el servicio")
    print("  journalctl -u jsbach -f      # Ver logs en tiempo real")
