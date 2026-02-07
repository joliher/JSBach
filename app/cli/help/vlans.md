# VLANS(8) -- Manual de usuario de JSBach

## NOMBRE
    vlans - Creación y gestión de redes virtuales (VLANs)

## SINOPSIS
    **vlans** [ACCIÓN] [OPCIÓN]...

## DESCRIPCIÓN
    El módulo **vlans** permite segmentar la red física en múltiples redes lógicas independientes. Gestiona la creación de interfaces virtuales en el kernel y la asignación de sus respectivos rangos de direcciones IP.

## ACCIONES

    **status**
        Muestra el listado de VLANs creadas y su estado operacional actual.

    **config** --action [add|remove|show] [OPCIONES]
        Administra la base de datos de configuración persistente.
        
        **--action add**
            Requiere: `--id ID` (1-4094), `--name NOMBRE`, `--ip_interface IP/MASK`, `--ip_network RED/MASK`.
            Ejemplo: `vlans config --action add --id 10 --name Gestion --ip_interface 192.168.10.1/24 --ip_network 192.168.10.0/24`
            
        **--action remove**
            Requiere: `--id ID`. Elimina la VLAN de la base de datos.
            
        **--action show**
            Lista toda la configuración guardada.

    **start**
        Levanta operacionalmente las interfaces virtuales (`vlan.X`) y asigna las IPs según la configuración.

    **stop**
        Detiene y elimina todas las interfaces virtuales del sistema.

    **restart**
        Recarga la segmentación de red (equivale a stop + start).

## EJEMPLOS
    vlans config --action add --id 20 --name Invitados --ip_interface 10.0.20.1/24 --ip_network 10.0.20.0/24
    vlans start
    vlans status

## NOTAS
    - El uso del formato CIDR (ej: /24) es obligatorio para IPs y redes.
    - Se recomienda no utilizar IDs reservados o el ID 1 (usado por defecto en la WAN/Bridge).
