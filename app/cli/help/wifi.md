# Módulo Wi-Fi (wifi)

Gestiona el punto de acceso inalámbrico del sistema.

## Acciones Comunes

### wifi status
Muestra el estado actual del punto de acceso (Activo, Inactivo o Incompatible).

### wifi start
Inicia el servicio hostapd y configura la interfaz inalámbrica.
Asegúrese de configurar SSID y Password antes del primer arranque.

### wifi stop
Detiene el servicio hostapd y libera la interfaz.

### wifi restart
Reinicia el servicio Wi-Fi.

## Configuración

### wifi config
Ajusta los parámetros de la red inalámbrica.

**Parámetros:**
- `--ssid` : Nombre de la red Wi-Fi.
- `--password` : Contraseña (WPA2-PSK).
- `--channel` : Canal (1-11 para 2.4G, 36+ para 5G).
- `--hw_mode` : Modo de hardware ('g' para 2.4G, 'a' para 5G).
- `--interface` : Interfaz de red física (ej: wlp3s0, wlan0).
- `--security` : Protocolo de seguridad (`open`, `wpa2`, `wpa3`, `mixed`).
- `--ip_address` : IP del router en la red Wi-Fi (ej: 10.0.99.1).
- `--netmask` : Máscara de red (ej: 255.255.255.0).
- `--dhcp_start` : Inicio del rango DHCP.
- `--dhcp_end` : Fin del rango DHCP.

**Ejemplo:**
  wifi config --ssid "MiRouterJSBach" --password "clave_segura_123" --security "wpa2"
  wifi config --interface wlan0 --security "open"

> [!NOTE]
> Es necesario reiniciar el módulo (`wifi restart`) para que los cambios de configuración surtan efecto.
