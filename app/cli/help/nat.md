# NAT(8) -- Manual de usuario de JSBach

## NOMBRE
    nat - Configuración de Masquerade para compartir conexión a Internet

## SINOPSIS
    **nat** [ACCIÓN] [OPCIÓN]...

## DESCRIPCIÓN
    El módulo **nat** implementa la traducción de direcciones de red (Network Address Translation) para permitir que los dispositivos de la red local (LAN) compartan una única dirección IP pública hacia Internet (WAN). Utiliza la funcionalidad *Masquerade* de `iptables`.

## ACCIONES

    **status**
        Muestra el estado global del IP Forwarding en el sistema y las reglas de Masquerade activas en la tabla NAT.

    **config** --wan_interface IFACE --lan_interfaces IFACES
        Define las interfaces física involucradas en el ruteo.
        `--lan_interfaces` acepta múltiples nombres separados por comas.
        Ejemplo: `nat config --wan_interface eno1 --lan_interfaces vlan.10,vlan.20`

    **start**
        Activa el forwarding en el kernel y aplica las reglas de Masquerade.

    **stop**
        Desactiva el forwarding y limpia todas las reglas de la tabla NAT relacionadas con el sistema.

    **restart**
        Recarga la configuración técnica del ruteo.

## EJEMPLOS
    nat config --wan_interface eno1 --lan_interfaces vlan.1
    nat start
    nat status

## NOTAS
    - La interfaz WAN debe estar operativa y con IP asignada previamente.
    - El IP Forwarding es un parámetro global del sistema kernel.
