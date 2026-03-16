# JSBach V4.7

**Sistema de gestión y administración de router con interfaz web y CLI**

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-green)](https://fastapi.tiangolo.com/)

---

## 📋 Descripción

JSBach V4.7 es un sistema completo de gestión de router que permite configurar y administrar servicios de red a través de dos interfaces:

- **🌐 Interfaz Web** (puerto 8100): Panel de administración con interfaz gráfica
- **⌨️ Interfaz CLI** (puerto 2200): Terminal interactivo vía TCP

### Módulos disponibles

- **WAN**: Configuración de interfaz de red externa (DHCP/Estática)
- **VLANs**: Creación y gestión de redes virtuales
- **Firewall**: Gestión de reglas de seguridad y whitelist por VLAN
- **NAT**: Network Address Translation para enmascaramiento de red
- **DMZ**: Zona desmilitarizada para servicios expuestos
- **Expect**: Automatización de sesiones remotas y ejecución de comandos
- **Tagging**: Etiquetado de tráfico VLAN en interfaces físicas
- **Ebtables**: Aislamiento de VLANs a nivel de capa 2 (Ethernet)

---

## 🚀 Instalación

### Requisitos

- Sistema operativo: **Linux** (Debian/Ubuntu recomendado)
- Python 3.8+
- Permisos de **root** para la instalación

### Proceso de instalación

1. **Clonar el repositorio**:
```bash
git clone https://github.com/joliher/JSBach
cd JSBach
```

2. **Ejecutar el instalador como root**:
```bash
sudo python3 scripts/install/install.py
```

3. **Configurar durante la instalación**:
   - Ruta de instalación (por defecto: `/opt/JSBach`)
   - Puerto web (por defecto: `8100`)
   - Usuario y contraseña de administración

### ¿Qué hace el instalador?

- ✅ Instala dependencias del sistema (python3, python3-pip, python3-venv)
- ✅ Crea el usuario del sistema **jsbach**
- ✅ Copia los archivos del proyecto a `/opt/JSBach`
- ✅ Crea un entorno virtual Python
- ✅ Instala paquetes Python (FastAPI, uvicorn)
- ✅ Configura permisos de archivos
- ✅ Crea servicios systemd (`jsbach.service` y `jsbach-cli.service`)
- ✅ Configura **sudoers** para comandos de red necesarios
- ✅ Crea archivo de autenticación en `config/cli_users.json`

### Servicios systemd

JSBach utiliza dos servicios interconectados:
- `jsbach.service`: Motor principal y servidor web (puerto 8100)
- `jsbach-cli.service`: Servidor CLI (puerto 2200). Depende de `jsbach.service`.

El instalador crea una unidad systemd separada para la CLI (`jsbach-cli.service`) con su propio `ExecStart` y `WorkingDirectory`. Esto permite gestionar la CLI como servicio independiente, aunque la unidad esta vinculada a `jsbach.service` (`BindsTo`/`PartOf`/`After`), por lo que si detienes `jsbach.service` tambien se detendra `jsbach-cli.service`.

```bash
# Ver estado de los servicios
sudo systemctl status jsbach
sudo systemctl status jsbach-cli

# Iniciar/Detener/Reiniciar (afecta a ambos)
sudo systemctl restart jsbach

# Gestion independiente del CLI
sudo systemctl start jsbach-cli
sudo systemctl stop jsbach-cli
sudo systemctl restart jsbach-cli

# Ver logs en tiempo real
sudo journalctl -u jsbach -f
sudo journalctl -u jsbach-cli -f
```

El servicio se ejecuta bajo el usuario **jsbach** y se inicia automáticamente al arrancar el sistema.

---

## 🌐 Acceso al sistema

### Interfaz Web

Accede desde tu navegador:

```
http://localhost:8100
```

Utilizar las credenciales configuradas durante la instalación

### Interfaz CLI

Conéctate vía TCP usando netcat o telnet:

```bash
# Usando netcat
nc localhost 2200

# Usando telnet
telnet localhost 2200
```

Credenciales: las mismas que la interfaz web.

---

## 📚 Documentación

### Ayuda desde el CLI

Para información detallada sobre comandos y uso del sistema:

- **Interfaz CLI**: Conecta al CLI y escribe `help` para ver todos los comandos disponibles
- **Ayuda por módulo**: Escribe `help <módulo>` (ej: `help wan`, `help firewall`, `help ebtables`)
- **Documentación detallada**: Cada módulo tiene documentación completa en `app/cli/help/`

### Módulos documentados

| Módulo | Archivo | Descripción |
|--------|---------|-------------|
| WAN | [wan.md](app/cli/help/wan.md) | Configuración de interfaz WAN (DHCP/Estática) |
| VLANs | [vlans.md](app/cli/help/vlans.md) | Creación y gestión de redes virtuales |
| Firewall | [firewall.md](app/cli/help/firewall.md) | Reglas de seguridad y whitelists |
| NAT | [nat.md](app/cli/help/nat.md) | Network Address Translation |
| DMZ | [dmz.md](app/cli/help/dmz.md) | Zona desmilitarizada |
| Expect | [expect.md](app/cli/help/expect.md) | Automatización de sesiones remotas |
| Tagging | [tagging.md](app/cli/help/tagging.md) | Etiquetado VLAN en interfaces |
| Ebtables | [ebtables.md](app/cli/help/ebtables.md) | Aislamiento L2 de VLANs |

### Pruebas

Ejecuta el suite de pruebas para validar la estabilidad del sistema:

```bash
cd /opt/JSBach/scripts/tests
sudo ../../venv/bin/python test_comprehensive.py
```

Este script realiza pruebas exhaustivas de:
- ✅ Gestión de WAN y conectividad
- ✅ Creación y eliminación de VLANs
- ✅ Reglas de Firewall (Whitelist, Aislamiento, Restricción)
- ✅ Configuración de NAT y DMZ
- ✅ Seguridad de capa 2 con Ebtables (PVLAN y MAC Whitelist)

---

## 🗑️ Desinstalación

Para desinstalar completamente JSBach V4.7:

```bash
cd /opt/JSBach/scripts/install
sudo python3 uninstall.py
```

El desinstalador te preguntará qué elementos deseas eliminar:

- ✅ Servicio systemd
- ✅ Reglas de iptables (opcional)
- ✅ Interfaces de red creadas (opcional)
- ✅ Configuración sudoers
- ✅ Directorio del proyecto
- ✅ Usuario jsbach (opcional)

**Nota**: Las dependencias del sistema (python3, pip) NO se eliminan ya que pueden ser usadas por otros programas.

---

## 🛠️ Desarrollo

### Estructura del proyecto

```
JSBach/
├── app/
│   ├── cli/          # Interfaz CLI (Servidor, Parser, Sesiones)
│   │   ├── help/     # Documentación de módulos (Markdown)
│   │   └── cli_server.py  # Punto de entrada del servicio CLI
│   ├── controllers/  # Controladores FastAPI (API y Rutas)
│   ├── core/         # Lógica de red (WAN, NAT, Firewall, etc.)
│   └── utils/        # Helpers, validaciones y logs
├── config/           # Archivos JSON de configuración persistente
├── scripts/          # Scripts de instalación y tests
│   ├── install/      # Instalación y desinstalación
│   └── tests/        # Suites de prueba
├── logs/             # Registro de actividad por componente
├── web/              # Interfaz gráfica (HTML, CSS, JS)
├── main.py           # Punto de entrada del servidor web
└── cli_server.py     # Script de arranque rápido para CLI
```

### Tecnologías utilizadas

-   **Backend**: Python 3.8+, FastAPI, Uvicorn
-   **Frontend**: HTML5, CSS3 modular, JavaScript vanilla
-   **CLI**: asyncio, socket TCP (puerto 2200)
-   **Networking**: iptables, iproute2, ebtables
-   **Sistema**: systemd, sudoers

### Arquitectura

-   **Helpers centralizados**: Módulos compartidos en `app/utils/` para config, validación y logging
-   **API RESTful**: Endpoints en `/admin/` para gestión de módulos
-   **Frontend modular**: CSS y JavaScript embebido en cada página HTML
-   **Autenticación**: Sistema de sesiones con middleware de protección
-   **Logs estructurados**: Registro de acciones por módulo en `logs/`

---

## ⚙️ Características Técnicas

### Backend Modularizado

-   **Helpers centralizados**: Todas las funciones comunes (carga de configs, validación, logging) en `app/utils/`
-   **Reducción de código duplicado**: ~1,200 líneas de código reutilizable
-   **Gestión de errores consistente**: Manejo uniforme en todos los módulos
-   **Logging estructurado**: Registro detallado de todas las acciones

### Frontend Modular

-   **CSS separado**: 5 archivos CSS modulares (global, buttons, cards, forms, header)
-   **JavaScript separado**: 2 archivos JS (app.js, utils.js)
-   **Sin dependencias externas**: HTML/CSS/JS vanilla, sin frameworks
-   **Responsive**: Diseño adaptable a diferentes resoluciones

### API RESTful

-   **Endpoints documentados**: API completa en `/admin/`
-   **Autenticación por sesión**: Middleware de protección
-   **Respuestas JSON**: Formato estándar para todas las respuestas
-   **Gestión de errores**: Códigos HTTP apropiados (200, 400, 404, etc.)

### Seguridad Proactiva
-   **Cadena de Seguridad Unificada**: Gestión centralizada de Blacklist y Whitelist en switches.
-   **Shadow ACL (Ping-Pong)**: Técnica de doble buffer (IDs 100/101) para cambios atómicos sin "ventanas de red abierta".
-   **Hardening de Scripts**: Detección determinista de errores del CLI y manejo inteligente de prompts.

### Seguridad

-   **Autenticación obligatoria**: Todas las rutas protegidas por login
-   **Hashing de contraseñas**: SHA256 para almacenamiento seguro
-   **Validación de inputs**: Sanitización de parámetros en todos los módulos
-   **Logs de auditoría**: Registro de todas las acciones administrativas

---

**JSBach V4.7** - Sistema profesional de gestión de router 🚀