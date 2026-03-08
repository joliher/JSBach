# WAN(8) -- Manual de usuario de JSBach

## NOMBRE
    wan - Gestión de la interfaz de red externa (Internet)

## SINOPSIS
    **wan** [ACCIÓN] [OPCIÓN]...

## DESCRIPCIÓN
    El módulo **wan** configura y controla el enlace de salida a Internet a través de una interfaz física (ej: eth0, eno1, etc.). Soporta direccionamiento dinámico (DHCP) y estático.

## ACCIONES

    **status**
        Muestra la información actual de red (IP, Máscara, GW) y diagnostica la conectividad externa.

    **config** --mode [dhcp|static] --interface IFACE [OPCIONES]
        Establece la configuración técnica de la interfaz.
        
        **--mode dhcp**
            Obtiene la configuración automáticamente del proveedor.
            
        **--mode static**
            Requiere especificar manualmente: `--ip`, `--netmask`, `--gateway` y `--dns`.

    **start**
        Habilita la interfaz, aplica la configuración y establece las rutas por defecto.

    **stop**
        Baja la interfaz y limpia las rutas asociadas.

    **restart**
        Reinicia la conexión WAN para aplicar cambios.

    **block** --ip IP
        Bloquea el acceso a Internet para una IP interna específica.
        Ejemplo: `wan block --ip 192.168.1.50`

    **unblock** --ip IP
        Restaura el acceso a Internet para una IP previamente bloqueada.
        Ejemplo: `wan unblock --ip 192.168.1.50`

    **traffic_log** --status [on|off]
        Activa o desactiva el registro (LOG) de flujos de salida hacia la WAN.
        Los logs se pueden visualizar en `dmesg` o `/var/log/syslog` con el prefijo `[JSB-WAN-OUT]`.

    **top**
        Muestra los 10 principales consumidores de ancho de banda (IPs internas) que salen por la WAN.
        Requiere que el módulo haya estado activo para acumular estadísticas.

## EJEMPLOS
    wan config --mode static --interface dummy0 --ip 10.0.0.2 --netmask 24 --gateway 10.0.0.1
    wan status
    wan block --ip 192.168.1.100
    wan top
    wan traffic_log --status on

## NOTAS
    - Los cambios en **config** no surten efecto hasta ejecutar **restart** o **start**.
    - La WAN es una dependencia crítica para el resto de módulos del sistema.
