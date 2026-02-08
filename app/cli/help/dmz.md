# DMZ(8) -- Manual de usuario de JSBach

## NOMBRE
    dmz - Gestión de redirección de puertos y protección de servidores expuestos

## SINOPSIS
    **dmz** [ACCIÓN] [OPCIÓN]...

## DESCRIPCIÓN
    El módulo **dmz** permite publicar servicios internos hacia Internet mediante redirección de puertos (DNAT). También proporciona capas adicionales de aislamiento para proteger el router y otras redes de hosts que se encuentren en la zona desmilitarizada.

## ACCIONES

    **status**
        Lista los destinos (IP:Puerto:Protocolo) configurados, su estado de aislamiento y estadísticas de tráfico.

    **config** --ip IP --port PUERTO --protocol [tcp|udp]
        Crea una nueva regla de redirección de puerto hacia un servidor interno.
        Ejemplo: `dmz config --ip 192.168.3.10 --port 80 --protocol tcp`

    **eliminar** --ip IP --port PUERTO --protocol PROTO
        Borra una regla de redirección específica y limpia su cortafuegos asociado.

    **start**
        Activa operacionalmente todas las reglas de redirección (DNAT) y permite el flujo en la cadena FORWARD.

    **stop**
        Limpia todas las redirecciones y cortafuegos asociados a la DMZ.

    **restart**
        Reinicia el subsistema de redirección de puertos.

    **aislar** --ip IP
        Bloquea preventivamente todo el tráfico de red del host especificado (WAN <-> Host y Host <-> Router).

    **desaislar** --ip IP
        Restaura la conectividad normal del servidor en la DMZ.

## EJEMPLOS
    dmz config --ip 192.168.10.100 --port 443 --protocol tcp
    dmz aislar --ip 192.168.10.100
    dmz status

## NOTAS
    - El aislamiento DMZ es una medida proactiva para contener hosts potencialmente comprometidos.
    - Se requiere que **WAN**, **VLANs**, **Tagging** y **Firewall** estén activos para operar DMZ.
    - Las IPs de destino deben pertenecer a rangos de VLANs activas.
