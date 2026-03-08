# JSBach V4.2 — Test Suite

## Estructura

```
scripts/tests/
├── wan_test.py                    # Test unitario: módulo WAN
├── vlans_test.py                  # Test unitario: módulo VLANs
├── tagging_test.py                # Test unitario: módulo Tagging
├── firewall_test.py               # Test unitario: módulo Firewall
├── nat_test.py                    # Test unitario: módulo NAT
├── wifi_test.py                   # Test unitario: módulo Wi-Fi (lifecycle)
├── integration_general.py         # Test integración: orquestación directa (API)
├── integration_cli.py             # Test integración: orquestación CLI (hardened)
└── README_TESTS.md                # Este fichero
```

## Tests de Integración

### `integration_general.py` — Orquestación Directa (5 tests)
Llama directamente a las funciones Python de cada módulo (sin CLI).
Verifica el ciclo completo: setup → start → isolate → restrict → stop → cleanup.

```bash
sudo /opt/JSBach_V4.2/venv/bin/python3 scripts/tests/integration_general.py
```

### `integration_cli.py` — Orquestación CLI Hardened (2 tests)
Usa el script Expect `app/modules/expect/scripts/master_cli_test.exp` para controlar todos los módulos
a través de la CLI interactiva (puerto 2200). Incluye:
- 7 comandos de hardening (isolate, restrict, whitelist, DMZ isolate, tagging isolate)
- Verificación exhaustiva del kernel (iptables, ebtables, IPs, bridge, procesos)
- Teardown sincronizado con verificación de limpieza

```bash
sudo /opt/JSBach_V4.2/venv/bin/python3 scripts/tests/integration_cli.py
```

## Tests Unitarios por Módulo

Cada test verifica el ciclo de vida del módulo individual (config → start → status → stop).
Requieren `sudo` y se ejecutan sobre interfaces dummy.

```bash
sudo /opt/JSBach_V4.2/venv/bin/python3 scripts/tests/wan_test.py
sudo /opt/JSBach_V4.2/venv/bin/python3 scripts/tests/vlans_test.py
sudo /opt/JSBach_V4.2/venv/bin/python3 scripts/tests/tagging_test.py
sudo /opt/JSBach_V4.2/venv/bin/python3 scripts/tests/firewall_test.py
sudo /opt/JSBach_V4.2/venv/bin/python3 scripts/tests/nat_test.py
sudo /opt/JSBach_V4.2/venv/bin/python3 scripts/tests/wifi_test.py
```

## Requisitos

- Ejecutar como `root` o con `sudo`
- Servicio `jsbach` activo (`systemctl restart jsbach` antes de cada ejecución)
- No se requiere hardware de red real (todo usa interfaces `dummy`)

## Orden recomendado

1. `systemctl restart jsbach`
2. Tests unitarios por módulo (en cualquier orden)
3. `integration_general.py`
4. `integration_cli.py`
