# 🔷 Módulo DHCP (dnsmasq)

Gestiona la asignación dinámica de IPs y la caché DNS para las redes internas.

## Acciones Comunes

### ### dhcp start
Inicia el servidor dnsmasq con la configuración generada.
  dhcp start

### ### dhcp stop
Detiene el servidor dnsmasq.
  dhcp stop

### ### dhcp status
Muestra el estado del servicio, PIDs y últimos logs.
  dhcp status

### ### dhcp restart
Reinicia el servicio DHCP.
  dhcp restart

### ### dhcp list_leases
Muestra las IPs asignadas actualmente y sus MACs.
  dhcp list_leases

## Configuración

### ### dhcp config
Configura parámetros globales del servidor DHCP.

**Parámetros:**
- `--dns`: Lista de servidores DNS upstream separados por comas.
- `--lease_time`: Tiempo de concesión (ej: 12h, 24h).
- `--vlan_id`: ID de la VLAN para configurar rangos específicos.
- `--start`: IP inicial del rango (requiere --vlan_id).
- `--end`: IP final del rango (requiere --vlan_id).
- `--dns`: DNS específicos para esta VLAN (requiere --vlan_id).

**Ejemplos:**
  dhcp config --dns "8.8.8.8, 1.1.1.1" --lease_time 24h
  dhcp config --vlan_id 3 --start 10.0.3.50 --end 10.0.3.150 --dns "9.9.9.9"
