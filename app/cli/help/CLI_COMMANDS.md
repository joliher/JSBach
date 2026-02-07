# JSBACH(8) -- Interfaz de Gestión de Línea de Comandos

## NOMBRE
    jsbach - Shell interactivo y servidor de comandos TCP para el router JSBach

## DESCRIPCIÓN
    La CLI de JSBach permite administrar todos los subsistemas del sistema de red (WAN, VLANs, Firewall, etc.). Ofrece una interfaz unificada accesible localmente o mediante conexiones TCP en el puerto 2200.

## CONEXIÓN
    El sistema requiere autenticación previa mediante usuario y contraseña (SHA256).
    `nc localhost 2200`
    `nc <ip-router> 2200` (Remoto)

## MÓDULOS DISPONIBLES
    **wan**(8)        Gestión del enlace externo a Internet.
    **nat**(8)        Compartición de conexión (Masquerade).
    **vlans**(8)      Segmentación de redes virtuales.
    **tagging**(8)    Configuración de puertos físicos (Access/Trunk).
    **firewall**(8)   Seguridad, filtrado y aislamiento por VLAN.
    **ebtables**(8)   Seguridad de capa 2 y Whitelist MAC.
    **dmz**(8)        Redirección de puertos y servicios públicos.
    **expect**(8)     Automatización remota de switches.

## COMANDOS ESPECIALES
    **help**          Muestra esta ayuda general de referencia.
    **help** <módulo> Detalla las acciones y parámetros de un componente.
    **exit** / **quit**   Cierra la sesión y desconecta del puerto 2200.

## EJEMPLOS
    jsbach@admin> wan status
    jsbach@admin> help firewall
    jsbach@admin> firewall aislar --vlan_id 1

## NOTAS
    - La sesión tiene un tiempo de espera de inactividad de 300 segundos.
    - Se requiere el uso del formato Long-Option (`--param valor`) para flags.
    - Los registros de todas las acciones se almacenan en la carpeta `/logs`.
