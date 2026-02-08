# EXPECT(8) -- Manual de usuario de JSBach

## NOMBRE
    expect - Automatización y gestión de switches remotos

## SINOPSIS
    **expect** [ACCIÓN] [OPCIÓN]...

## DESCRIPCIÓN
    El módulo **expect** automatiza la configuración de switches (Cisco, TP-Link) mediante scripts interactivos. Permite gestionar puertos, VLANs y seguridad física sin necesidad de acceder manualmente a la consola del dispositivo.

## ACCIONES

    **status**
        Muestra información sobre el estado del módulo, perfiles cargados y estadísticas de ejecución.

    **auth** --ip IP --user USUARIO [--password PASS]
        Configura y almacena de forma segura las credenciales para un dispositivo específico.
        La contraseña es opcional y se puede dejar vacía si el equipo lo permite.

    **config** --ip IP --actions "ACCIONES" [--profile PERFIL] [--dry-run]
        Aplica configuraciones técnicas basadas en sintaxis de bloques.
        Use '/' para separar múltiples bloques (ej: puerto y global).
        
        **Sintaxis de Bloque**: `ports:<RANGO>,mode:<MODO>,<PARAMETROS>`
        **Jerarquía**: El parámetro `mode` debe definirse ANTES que vlan/tag/untag.
        
        Ejemplo: `expect config --ip 1.1.1.1 --actions "ports:1-10,mode:access,vlan:100"`

    **reset** --ip IP [--profile PERFIL]
        Realiza un remocio de configuración (*Soft Reset*) de todos los puertos físicos.

    **port-security** --ip IP --ports RANGO --macs LISTA [--dry-run]
        Establece filtrado de MAC estricto en los puertos indicados.
        `--macs` acepta direcciones separadas por espacios.

## EJEMPLOS
    expect auth --ip 10.0.0.5 --user admin --password secret
    expect config --ip 10.0.0.5 --actions "hostname:SW-PISO1 / ports:1,mode:trunk,tag:10,20"
    expect port-security --ip 10.0.0.5 --ports 2-4 --macs "AA:BB:CC:DD:EE:FF"

## NOTAS
    - El modo `access` solo permite el parámetro `vlan`.
    - Los modos `trunk` y `general` requieren `tag` o `untag`.
    - Use `--dry-run` para visualizar el script generado antes de enviarlo al switch.
