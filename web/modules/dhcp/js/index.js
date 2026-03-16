// web/modules/dhcp/js/index.js

async function fetchStatus() {
    const output = document.getElementById('output');
    if (!output) return;
    const loading = document.getElementById('loading');

    if (loading) loading.style.display = 'block';
    output.textContent = 'Consultando estado...';

    try {
        const response = await fetch('/admin/dhcp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'status', params: {} }),
            credentials: 'include'
        });

        const data = await response.json();
        if (response.ok) {
            output.textContent = data.message || 'Estado obtenido';
        } else {
            output.textContent = 'Error: ' + (data.message || data.detail || 'Fallo en la consulta');
        }
    } catch (err) {
        output.textContent = 'Error de conexión: ' + err.message;
        if (window.showToast) showToast('Error al conectar con el servidor');
    } finally {
        if (loading) loading.style.display = 'none';
    }
}

async function ejecutarAccion(action) {
    const output = document.getElementById('output');
    const loading = document.getElementById('loading');

    if (loading) loading.style.display = 'block';
    if (output) output.textContent = `Ejecutando ${action}...`;

    try {
        const response = await fetch('/admin/dhcp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: action, params: {} }),
            credentials: 'include'
        });

        const data = await response.json();
        if (response.ok && data.success) {
            if (output) output.textContent = data.message || 'Acción completada con éxito';
            if (window.showToast) showToast(`DHCP: ${action} completado`, 'success');
        } else {
            const errorMsg = data.message || data.detail || 'Error desconocido';
            if (output) output.textContent = 'ERROR: ' + errorMsg;
            if (window.showToast) showToast('Error: ' + errorMsg);
        }
    } catch (err) {
        if (output) output.textContent = 'Error de comunicación: ' + err.message;
        if (window.showToast) showToast('Error de comunicación');
    } finally {
        if (loading) loading.style.display = 'none';
        // Limpiar URL después de ejecutar
        window.history.replaceState({}, document.title, window.location.pathname);
    }
}

async function saveConfig() {
    const dns = document.getElementById('dns-servers').value;
    const lease = document.getElementById('lease-time').value;

    // Recolectar todas las configuraciones de VLAN de la tabla
    const vlanConfigs = {};
    const rows = document.querySelectorAll('#vlan-table-body tr');

    rows.forEach(row => {
        const startInput = row.querySelector('input[id^="start-"]');
        if (startInput) {
            const vid = startInput.id.replace('start-', '');
            vlanConfigs[vid] = {
                start: document.getElementById(`start-${vid}`).value,
                end: document.getElementById(`end-${vid}`).value,
                dns: document.getElementById(`dns-${vid}`).value
            };
        }
    });

    try {
        const response = await fetch('/admin/dhcp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                action: 'config',
                params: {
                    dns: dns,
                    lease_time: lease,
                    vlan_configs: vlanConfigs
                }
            }),
            credentials: 'include'
        });

        const data = await response.json();
        if (response.ok && data.success) {
            showToast('Configuraciones guardadas correctamente (Global + VLANs)', 'success');
        } else {
            showToast('Error: ' + (data.message || data.detail || 'Error desconocido'));
        }
    } catch (err) {
        showToast('Error de red');
    }
}

// --- PER-VLAN CONFIGURATION ---

async function loadVlansAndConfig() {
    const tbody = document.getElementById('vlan-table-body');
    if (!tbody) return;

    try {
        // 1. Fetch VLANs
        const vlanRes = await fetch('/admin/config/vlans/vlans.json', { credentials: 'include' });
        const vlanData = await vlanRes.json();
        const vlans = vlanData.vlans || [];

        // Ordenar por ID
        vlans.sort((a, b) => a.id - b.id);

        // 2. Fetch DHCP Config
        const dhcpRes = await fetch('/admin/config/dhcp/dhcp.json', { credentials: 'include' });
        const dhcpData = await dhcpRes.json();
        const vlanConfigs = dhcpData.vlan_configs || {};

        if (vlans.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;">No hay VLANs activas.</td></tr>';
            return;
        }

        tbody.innerHTML = '';
        vlans.forEach(vlan => {
            const vid = vlan.id.toString();
            const config = vlanConfigs[vid] || {};

            // Guessing default range (router + 100 to router + 200)
            const ipBase = vlan.ip_interface.split('.')[0] + '.' + vlan.ip_interface.split('.')[1] + '.' + vlan.ip_interface.split('.')[2];
            const defaultStart = config.start || `${ipBase}.100`;
            const defaultEnd = config.end || `${ipBase}.200`;
            const defaultDns = config.dns || '';

            const row = document.createElement('tr');
            row.innerHTML = `
                <td><strong>VLAN ${vlan.id}</strong><br><small>${vlan.name}</small></td>
                <td><code style="background:rgba(255,255,255,0.05); padding:2px 5px; border-radius:4px;">${vlan.ip_interface}</code></td>
                <td><input type="text" id="start-${vid}" value="${defaultStart}" class="inline-input" style="width:120px;"></td>
                <td><input type="text" id="end-${vid}" value="${defaultEnd}" class="inline-input" style="width:120px;"></td>
                <td><input type="text" id="dns-${vid}" value="${defaultDns}" class="inline-input" style="width:180px;" placeholder="Vacío = Puerta Enlace"></td>
            `;
            tbody.appendChild(row);
        });
    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:var(--error);">Error al cargar datos.</td></tr>';
    }
}

async function saveVlanConfig(vlanId) {
    const start = document.getElementById(`start-${vlanId}`).value;
    const end = document.getElementById(`end-${vlanId}`).value;
    const dns = document.getElementById(`dns-${vlanId}`).value;

    try {
        const response = await fetch('/admin/dhcp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                action: 'config',
                params: {
                    vlan_id: vlanId,
                    start: start,
                    end: end,
                    dns: dns
                }
            }),
            credentials: 'include'
        });

        const data = await response.json();
        if (response.ok && data.success) {
            showToast(`VLAN ${vlanId}: Configuración guardada`, 'success');
        } else {
            showToast('Error: ' + (data.message || data.detail || 'Error desconocido'));
        }
    } catch (err) {
        showToast('Error de red');
    }
}

// Initialization check for config page
if (document.getElementById('vlan-table-body')) {
    loadVlansAndConfig();
}
