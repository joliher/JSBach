// Esperar a que el DOM esté listo
document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('dmzForm');
    const resultDiv = document.getElementById('result');
    const firewallWarning = document.getElementById('firewallWarning');

    if (!form) {
        console.error('DMZ Config: form #dmzForm no encontrado. Abortando inicialización.');
        return;
    }

    // Verificar estado del firewall al cargar la página
    async function checkFirewallStatus() {
        try {
            const response = await fetch('/config/firewall/firewall.json', { credentials: 'include' });
            if (!response.ok) {
                firewallWarning.style.display = 'block';
                const submitBtn = form.querySelector('button[type="submit"]');
                if (submitBtn) submitBtn.disabled = true;
                return false;
            }

            const firewallData = await response.json();
            const isActive = firewallData.status === 1;

            const submitBtn = form.querySelector('button[type="submit"]');
            if (!isActive) {
                firewallWarning.style.display = 'block';
                if (submitBtn) {
                    submitBtn.disabled = true;
                    submitBtn.style.opacity = '0.5';
                    submitBtn.style.cursor = 'not-allowed';
                }
            } else {
                firewallWarning.style.display = 'none';
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.style.opacity = '1';
                    submitBtn.style.cursor = 'pointer';
                }
            }

            return isActive;
        } catch (err) {
            firewallWarning.style.display = 'block';
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) submitBtn.disabled = true;
            return false;
        }
    }

    function showResult(message, isSuccess) {
        resultDiv.textContent = message;
        resultDiv.className = isSuccess ? 'success' : 'error';
        resultDiv.style.display = 'block';

        setTimeout(() => {
            resultDiv.style.display = 'none';
        }, 5000);
    }

    // Función para obtener la configuración de la VLAN DMZ
    async function getDmzNetwork() {
    try {
        // Leer directamente desde el status de DMZ que ya tiene acceso a VLANs
        const response = await fetch('/config/vlans/vlans.json');

        if (!response.ok) {
            return null;
        }

        const vlansData = await response.json();

        // Buscar la VLAN 2 (DMZ)
        const dmzVlan = vlansData.vlans.find(v => v.id === 2);
        if (!dmzVlan || !dmzVlan.ip) {
            return null;
        }

        return dmzVlan.ip; // Retorna algo como "192.168.2.1/25"
    } catch (err) {
        return null;
    }
}

// Función para validar si una IP está en una red
function isIpInNetwork(ip, networkCidr) {
    try {
        const [ipAddr, ipMask] = ip.split('/');
        const [netAddr, netMask] = networkCidr.split('/');

        const ipNum = ipAddr.split('.').reduce((acc, octet) => (acc << 8) + parseInt(octet), 0) >>> 0;
        const netNum = netAddr.split('.').reduce((acc, octet) => (acc << 8) + parseInt(octet), 0) >>> 0;

        const mask = (0xFFFFFFFF << (32 - parseInt(netMask))) >>> 0;
        const ipMaskNum = (0xFFFFFFFF << (32 - parseInt(ipMask))) >>> 0;

        // Calcular la dirección de red y broadcast de la IP ingresada
        const ipNetwork = (ipNum & ipMaskNum) >>> 0;
        const ipBroadcast = (ipNetwork | ~ipMaskNum) >>> 0;

        // Calcular la dirección de red y broadcast de la red DMZ
        const networkAddr = (netNum & mask) >>> 0;
        const broadcastAddr = (networkAddr | ~mask) >>> 0;

        // Verificar que tanto la red como el broadcast de la IP estén dentro de la DMZ
        return ipNetwork >= networkAddr && ipBroadcast <= broadcastAddr;
    } catch (err) {
        return false;
    }
}

    const submitBtn = form.querySelector('button[type="submit"]');
    let submitting = false;
    if (!submitBtn) {
        console.warn('DMZ Config: botón de submit no encontrado en el formulario.');
    }

    form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (submitting) return; // bloquear reenvíos simultáneos
    submitting = true;
    if (submitBtn) submitBtn.disabled = true;

    const resetSubmit = () => {
        submitting = false;
        if (submitBtn) submitBtn.disabled = false;
    };

    const ip = document.getElementById('ip').value.trim();
    const port = parseInt(document.getElementById('port').value);
    const protocol = document.getElementById('protocol').value;

    if (!ip || !port || !protocol) {
        showResult('❌ Todos los campos son obligatorios', false);
        resetSubmit();
        return;
    }

    // Verificar que la IP NO contenga máscara
    if (ip.includes('/')) {
        showResult('❌ Error: la IP no debe incluir máscara de red. Introduzca solo la IP (ej: 192.168.2.10)', false);
        resetSubmit();
        return;
    }

    const octets = ip.split('.');

    // Validar formato de IP
    if (octets.length !== 4 || octets.some(o => isNaN(o) || parseInt(o) < 0 || parseInt(o) > 255)) {
        showResult('❌ Error: formato de IP inválido', false);
        resetSubmit();
        return;
    }

    const lastOctet = parseInt(octets[3]);

    if (lastOctet === 0 || lastOctet === 255) {
        showResult('❌ Error: la IP no puede terminar en 0 o 255', false);
        resetSubmit();
        return;
    }

    if (port < 1 || port > 65535) {
        showResult('❌ Puerto debe estar entre 1 y 65535', false);
        resetSubmit();
        return;
    }

    // Verificar si el puerto y protocolo ya están en uso
    try {
        const dmzResponse = await fetch('/config/dmz/dmz.json');
        if (dmzResponse.ok) {
            const dmzData = await dmzResponse.json();
            const destinations = dmzData.destinations || [];

            // Buscar si el puerto+protocolo ya están en uso
            const portInUse = destinations.find(dest =>
                dest.port === port &&
                dest.protocol === protocol &&
                dest.ip !== ip
            );

            if (portInUse) {
                showResult(`❌ El puerto ${port}/${protocol} ya está en uso por ${portInUse.ip}. Cada puerto solo puede redirigirse a un único destino.`, false);
                resetSubmit();
                return;
            }
        }
    } catch (err) {
        // Continuar con la validación del backend
    }

    const params = {
        ip: ip,
        port: port,
        protocol: protocol
    };

    let response = null;
    try {
        response = await fetch('/admin/dmz', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'include',
            body: JSON.stringify({
                action: 'add_destination',
                params: params
            })
        });
    } catch (err) {
        console.error('Error enviando petición a /admin/dmz:', err);
        showResult('❌ Error de red al comunicarse con el servidor', false);
        resetSubmit();
        return;
    }

    // submit button handler registered earlier

    if (!response) {
        showResult('❌ Sin respuesta del servidor', false);
        resetSubmit();
        return;
    }

    if (!response.ok) {
        // Intentar leer JSON de error (FastAPI devuelve {detail: ...}), caer a texto si no es JSON
        let errMsg = '';
        try {
            const j = await response.json();
            errMsg = j.detail || j.message || JSON.stringify(j);
        } catch (e) {
            try {
                errMsg = await response.text();
            } catch (e2) {
                errMsg = response.statusText || 'Error desconocido';
            }
        }
        showResult(`❌ Error ${response.status}: ${errMsg}`, false);
        resetSubmit();
        return;
    }

    let data = null;
    try {
        data = await response.json();
    } catch (err) {
        showResult('❌ Respuesta inválida del servidor', false);
        resetSubmit();
        return;
    }

    if (data && data.success) {
        showResult(`✅ ${data.message}`, true);
        form.reset();
    } else {
        const msg = (data && data.message) ? data.message : 'Error desconocido';
        showResult(`❌ ${msg}`, false);
    }

    resetSubmit();

    });

    // Verificar firewall al cargar la página
    checkFirewallStatus();
});