# EBTABLES(8) -- Manual de usuario de JSBach

## NOMBRE
    ebtables - Filtrado de capa 2 (MAC) y aislamiento Private VLAN (PVLAN)

## SINOPSIS
    **ebtables** [ACCIÓN] [OPCIÓN]...

## DESCRIPCIÓN
    El módulo **ebtables** gestiona el filtrado de tramas Ethernet en el bridge de red. Permite implementar políticas de seguridad basadas en direcciones MAC (Whitelist) y aislamiento de hosts en una misma VLAN (Private VLAN) para evitar ataques de red local.

## ACCIONES

    **status**
        Muestra si las reglas de filtrado están activas y el estado de aislamiento de cada VLAN.

    **start / stop / restart**
        Gestiona la activación global de las reglas de capa 2 en el kernel.

    **isolate** --vlan_id ID
        Activa el modo PVLAN: los hosts de la VLAN solo podrán comunicarse con la puerta de enlace (Internet), bloqueando el tráfico entre ellos.

    **unisolate** --vlan_id ID
        Desactiva el aislamiento de capa 2 en la VLAN indicada.

    **enable_whitelist / disable_whitelist**
        Activa o desactiva el filtrado estricto por MAC en la VLAN de administración (VLAN 1).

    **add_mac** --mac DIRECCIÓN
        Autoriza una dirección física (XX:XX:XX:XX:XX:XX) en la Whitelist.

    **remove_mac** --mac DIRECCIÓN
        Elimina el acceso a una MAC previamente autorizada.

    **show_whitelist**
        Lista todas las direcciones MAC autorizadas actualmente.

## EJEMPLOS
    ebtables isolate --vlan_id 10
    ebtables add_mac --mac AA:BB:CC:DD:EE:FF
    ebtables show_whitelist

## NOTAS
    - El aislamiento PVLAN previene ataques como ARP Spoofing y escaneo interno en el router.
    - El filtrado por MAC en este módulo solo afecta al bridge interno del router.
    - **RECOMENDACIÓN**: Para seguridad en puertos físicos de switches, utilice el módulo **expect**, que implementa la **Cadena de Seguridad Unificada (JSBACH_SECURITY)** directamente en el hardware.
    - Requiere que las interfaces estén configuradas en el módulo **Tagging**.
