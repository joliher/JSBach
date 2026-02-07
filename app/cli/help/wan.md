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

## EJEMPLOS
    wan config --mode dhcp --interface eno1
    wan config --mode static --interface eth0 --ip 80.25.10.5 --netmask 255.255.255.0 --gateway 80.25.10.1
    wan status

## NOTAS
    - Los cambios en **config** no surten efecto hasta ejecutar **restart** o **start**.
    - La WAN es una dependencia crítica para el resto de módulos del sistema.
