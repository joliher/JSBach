# Roadmap de Mejora - Seguridad JSBach V4.2

Este documento detalla las mejoras de seguridad recomendadas para futuras fases del proyecto JSBach.

## 1. Migración a SSH para Gestión de Switches
*   **Estado actual**: Se utiliza Telnet, lo que envía comandos y credenciales en texto plano por la red local.
*   **Mejora**: Implementar soporte para SSH en el módulo `expect`. Esto cifrará todo el tráfico entre el servidor JSBach y el hardware de red.

## 2. Implementación de HTTPS (TLS) para la Interfaz Web
*   **Estado actual**: La comunicación web es vía HTTP.
*   **Mejora**: Configurar un certificado SSL/TLS (vía Nginx como proxy inverso o directamente en Uvicorn) para cifrar las sesiones web y protegerlas de ataques de interceptación (Sniffing/MitM).

## 3. Registro de Auditoría (Audit Logs)
*   **Estado actual**: Los logs actuales son operacionales y rotan con frecuencia.
*   **Mejora**: Implementar un sistema de logs de auditoría inmutable que registre:
    *   Quién (usuario) realizó un cambio.
    *   Qué cambió (configuración antigua vs nueva).
    *   Cuándo (timestamp preciso).
    *   Desde dónde (IP de origen).

## 4. Gestión Centralizada de Secretos
*   **Estado actual**: Los secretos se guardan cifrados en disco con una llave maestra local.
*   **Mejora**: Evaluar el uso de un gestor de secretos (como HashiCorp Vault o servicios Cloud) para evitar que la llave maestra resida en el mismo sistema de archivos que la aplicación.

---
*Documento generado el 18 de Febrero de 2026*
