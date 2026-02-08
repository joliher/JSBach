# FIREWALL(8) -- Manual de usuario de JSBach

## NOMBRE
    firewall - Gestión de reglas de seguridad e iptables por VLAN

## SINOPSIS
    **firewall** [ACCIÓN] [OPCIÓN]...

## DESCRIPCIÓN
    El módulo **firewall** permite gestionar el filtrado de tráfico IP entre las distintas redes del sistema. Utiliza `iptables` internamente para aplicar políticas de seguridad, aislamiento de redes y restricciones de servicios en el router.

## ACCIONES

    **status**
        Muestra el estado actual del firewall, cadenas activas y estadísticas de iptables.

    **start**
        Inicializa las cadenas necesarias y aplica todas las reglas configuradas. Requiere que los módulos **WAN**, **VLANs** y **Tagging** estén activos.

    **stop**
        Desactiva el firewall, elimina las reglas aplicadas y limpia las cadenas.

    **restart**
        Realiza un reinicio completo del subsistema (equivalente a stop + start).

    **enable_whitelist** --vlan_id ID [--whitelist REGLAS]
        Activa el filtrado restrictivo por lista blanca en la VLAN indicada.
        `--whitelist` acepta reglas separadas por comas (ej: IP, IP/proto, IP:puerto, :puerto, /proto).

    **disable_whitelist** --vlan_id ID
        Desactiva la whitelist para la VLAN, permitiendo de nuevo todo el tráfico.

    **add_rule** --vlan_id ID --rule REGLA
        Añade una regla a la whitelist de una VLAN existente.

    **remove_rule** --vlan_id ID --rule REGLA
        Elimina una regla de la whitelist, denegando de nuevo su acceso.

    **aislar** --vlan_id ID
        Bloquea todo el acceso a Internet (FORWARD) para la red especificada.

    **desaislar** --vlan_id ID
        Restaura el acceso a Internet (sujeto a la configuración de whitelist).

    **restrict** --vlan_id ID
        Limita los servicios accesibles del router (solo DNS/DHCP/ICMP) para esa VLAN.

    **unrestrict** --vlan_id ID
        Elimina las restricciones del modo restrict en la VLAN indicada.

## EJEMPLOS
    firewall enable_whitelist --vlan_id 10 --whitelist 192.168.10.5,192.168.10.20
    firewall aislar --vlan_id 1
    firewall status

## NOTAS
    - El aislamiento (**aislar**) tiene prioridad máxima sobre cualquier regla de forwarding.
    - Las restricciones (**restrict**) solo afectan al tráfico dirigido a la IP del propio router.
    - Las VLANs 1 y 2 no permiten whitelist.
