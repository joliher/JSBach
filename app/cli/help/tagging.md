# TAGGING(8) -- Manual de usuario de JSBach

## NOMBRE
    tagging - Etiquetado de tráfico IEEE 802.1Q en puertos físicos

## SINOPSIS
    **tagging** [ACCIÓN] [OPCIÓN]...

## DESCRIPCIÓN
    El módulo **tagging** permite asociar interfaces físicas de hardware con las VLANs del sistema. Define qué puertos actúan como "Access" (tráfico sin etiquetas) o "Trunk" (mantiene etiquetas 802.1Q).

## ACCIONES

    **status**
        Muestra el mapeo actual de interfaces, su estado (UP/DOWN) y vinculación con el bridge `br0`.

    **config** --action [add|remove|show] [OPCIONES]
        Administra la asignación de puertos físicos.
        
        **--action add**
            Requiere: `--name IFACE`, `--vlan_untag ID` (para Access) o `--vlan_tag IDS` (para Trunk).
            Ejemplo Access: `tagging config --action add --name eth1 --vlan_untag 10`
            Ejemplo Trunk: `tagging config --action add --name eth2 --vlan_tag 10,20,30`
            
        **--action remove**
            Requiere: `--name IFACE`. Elimina la interfaz del sistema de tagging.
            
        **--action show**
            Muestra la configuración técnica de puentes y VLANs en el bridge.

    **start**
        Activa el motor de tagging, vincula las interfaces físicas al bridge y aplica las etiquetas.

    **stop**
        Detiene el etiquetado y devuelve las interfaces físicas a su estado original.

    **restart**
        Recarga la topología de red de capa 2.

## CONCEPTOS
    **Access Port (Untagged)**
        Utilizado para conectar PCs o servidores finales. El tráfico sale sin etiquetas.
        
    **Trunk Port (Tagged)**
        Utilizado para conectar otros switches. Mantiene las etiquetas 802.1Q para transportar múltiples VLANs por un solo cable.

## NOTAS
    - Una misma interfaz no puede ser simultáneamente Access y Trunk en este sistema.
    - Se requiere que el módulo **VLANs** esté activo previamente.
