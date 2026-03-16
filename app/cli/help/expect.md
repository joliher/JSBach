# EXPECT(8) -- Manual de usuario de JSBach

## NOMBRE
    expect - Automatización y gestión de switches remotos (V4.4)

## SINOPSIS
    **expect** [ACCIÓN] [OPCIÓN]...

## DESCRIPCIÓN
    El módulo **expect** permite la orquestación y control de switches físicos (Cisco, TP-Link). Esta versión introduce la **Arquitectura de Seguridad por Capas**, que permite aplicar políticas de aislamiento y confianza de forma independiente sobre diferentes objetivos (VLANs o Puertos).

    Características principales:
    - **Zero-Disk Execution**: Los comandos se inyectan directamente vía variables de entorno, eliminando el uso de archivos temporales sensibles.
    - **Shadow ACL (Ping-Pong) Multicapa**:
        - **Blacklist**: Utiliza IDs 100/101 para bloqueo global (Puertos 2-max).
        - **Whitelist**: Utiliza IDs 200/201 para control Zero-Trust (VLAN 1).
    - **Atomicidad**: El intercambio (BIND) de listas es atómico, garantizando que el switch nunca se quede sin protección durante la sincronización.

## ACCIONES

    **auth** --ip IP --user USUARIO [--password PASS]
        Configura y almacena las credenciales para un dispositivo.

    **mac_table** --ip IP
        Consulta la tabla de direcciones MAC activa en el switch (modo lectura rápida).

    **security_mode** --ip IP --mode blacklist|whitelist
        Cambia la política global del switch.
        **blacklist**: Permisivo. Bloquea solo MACs en 'isolate'.
        **whitelist**: Restrictivo. Bloquea todo excepto MACs autorizadas.
        Esta acción sincroniza inmediatamente el switch usando Shadow ACL.

    **isolate** --ip IP --mac MAC
        Aísla una MAC. Tiene prioridad absoluta sobre cualquier otra regla.
        Ej: `expect isolate --ip 10.0.1.5 --mac AA:BB:CC:DD:EE:FF`

    **unisolate** --ip IP --mac MAC
        Levanta el aislamiento de una dirección MAC.

    **add_to_whitelist** --ip IP --mac MAC
        Añade una MAC a la lista blanca local (sin aplicar al switch).

    **remove_from_whitelist** --ip IP --mac MAC
        Elimina una MAC de la lista blanca local.

    **apply_whitelist** --ip IP
        Sincroniza la lista blanca local y el modo de seguridad con el switch.
        Ejecuta el ciclo Shadow Swap (Ping-Pong) de forma atómica.

    **get_whitelist** --ip IP
        Consulta la whitelist y el modo de seguridad guardados para ese switch.

    **config** --ip IP --actions "ACCIONES" [--dry_run]
        Aplica configuraciones avanzadas mediante bloques (ej: VLANs, Puertos).

    **reset** --ip IP
        Limpia la configuración de los puertos y borra el estado de seguridad local.

    **get_state** [--ip IP]
        Muestra el estado completo (aislamientos, whitelist, modo) del sistema.

    **list_switches**
        Muestra los switches registrados y sus perfiles (Cisco, TP-Link, etc).

## EJEMPLOS
    expect security_mode --ip 10.0.1.5 --mode whitelist
    expect add_to_whitelist --ip 10.0.1.5 --mac 00:AA:BB:CC:DD:EE
    expect apply_whitelist --ip 10.0.1.5
    expect isolate --ip 10.0.1.5 --mac 11:22:33:44:55:66

## NOTAS
    - El aislamiento (Deny) siempre se procesa antes que la Whitelist (Permit).
    - Los nombres de las ACL en el switch siguen el patrón `JSBACH_SECURITY_{id}`.
    - Se utilizan alternativamente los IDs 100 y 101 para garantizar la atomicidad.
