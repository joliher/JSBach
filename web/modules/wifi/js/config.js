/* /web/modules/wifi/js/config.js */

async function loadConfig() {
    try {
        const response = await fetch('/admin/config/wifi/wifi.json', { credentials: 'include' });
        if (response.ok) {
            const cfg = await response.json();
            if (cfg.ssid && document.getElementById('ssid')) document.getElementById('ssid').value = cfg.ssid;
            if (cfg.password && document.getElementById('password')) document.getElementById('password').value = cfg.password;
            if (cfg.hw_mode && document.getElementById('hw_mode')) document.getElementById('hw_mode').value = cfg.hw_mode;
            if (cfg.channel && document.getElementById('channel')) document.getElementById('channel').value = cfg.channel;
            if (cfg.ip_address && document.getElementById('ip_address')) document.getElementById('ip_address').value = cfg.ip_address;
            if (cfg.netmask && document.getElementById('netmask')) document.getElementById('netmask').value = cfg.netmask;
            if (cfg.dhcp_start && document.getElementById('dhcp_start')) document.getElementById('dhcp_start').value = cfg.dhcp_start;
            if (cfg.dhcp_end && document.getElementById('dhcp_end')) document.getElementById('dhcp_end').value = cfg.dhcp_end;
            if (cfg.interface && document.getElementById('interface')) document.getElementById('interface').value = cfg.interface;
            if (cfg.security && document.getElementById('security')) {
                document.getElementById('security').value = cfg.security;
                togglePasswordField();
            }

            // Portal Cautivo
            if (cfg.portal_enabled !== undefined && document.getElementById('portal_enabled')) {
                document.getElementById('portal_enabled').checked = cfg.portal_enabled;
            }
            if (cfg.portal_port && document.getElementById('portal_port')) {
                document.getElementById('portal_port').value = cfg.portal_port;
            }

            // Cargar usuarios del portal
            if (document.getElementById('portal-users-table')) {
                await loadPortalUsers();
            }
        }
    } catch (error) {
        console.error("Error cargando configuración wifi:", error);
    } finally {
        // Cargar estado de seguridad adicional de firewall
        if (document.getElementById('btn-iso') || document.getElementById('btn-res')) {
            await loadSecurityState();
        }
        // Cargar MACs de ebtables (Blacklist)
        if (document.getElementById('mac-list-table')) {
            await loadWifiMacs();
        }
    }
}

async function loadSecurityState() {
    try {
        const response = await fetch('/admin/config/firewall/firewall.json', { credentials: 'include' });
        if (response.ok) {
            const fwCfg = await response.json();
            const wifiFw = fwCfg.wifi || { isolated: false, restricted: false };

            updateSecurityButton('btn-iso', wifiFw.isolated, 'Aislar (WAN)', 'Aislamiento Activo');
            updateSecurityButton('btn-res', wifiFw.restricted, 'Restringir', 'Restricción Activa');
        }
    } catch (error) {
        console.error("Error cargando estado de seguridad firewall:", error);
    }
}

function updateSecurityButton(id, isActive, inactiveLabel, activeLabel) {
    const btn = document.getElementById(id);
    if (!btn) return;

    if (isActive) {
        btn.textContent = activeLabel;
        btn.style.background = 'rgba(239, 68, 68, 0.2)';
        btn.style.color = 'var(--error)';
        btn.style.border = '1px solid var(--error)';
    } else {
        btn.textContent = inactiveLabel;
        btn.style.background = 'rgba(16, 185, 129, 0.1)';
        btn.style.color = 'var(--success)';
        btn.style.border = '1px solid var(--success)';
    }
}

async function toggleSecurity(type, btn) {
    const isIsolated = btn.id === 'btn-iso' && btn.textContent.includes('Activo');
    const isRestricted = btn.id === 'btn-res' && btn.textContent.includes('Activa');

    let action = '';
    if (type === 'isolate') {
        action = isIsolated ? 'unisolate' : 'isolate';
    } else if (type === 'restrict') {
        action = isRestricted ? 'unrestrict' : 'restrict';
    }

    btn.disabled = true;
    btn.textContent = '...';

    try {
        const response = await fetch('/admin/firewall', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: action, params: { module: 'wifi' } }),
            credentials: 'include'
        });
        const data = await response.json();
        if (data.success) {
            await loadSecurityState();
        }
    } catch (error) {
        console.error("Error toggling security:", error);
    } finally {
        btn.disabled = false;
    }
}

function togglePasswordField() {
    const security = document.getElementById('security').value;
    const passwordGroup = document.getElementById('password-group');
    if (!passwordGroup) return;

    if (security === 'open') {
        passwordGroup.style.display = 'none';
        document.getElementById('password').required = false;
    } else {
        passwordGroup.style.display = 'block';
        document.getElementById('password').required = true;
    }
}

async function loadWifiMacs() {
    const tableBody = document.getElementById('mac-list-table');
    if (!tableBody) return;
    tableBody.innerHTML = '<tr><td colspan="2" style="text-align: center; padding: 20px; color: var(--text-secondary);">Cargando MACs...</td></tr>';

    try {
        const response = await fetch('/admin/config/ebtables/ebtables.json', { credentials: 'include' });
        if (response.ok) {
            const ebCfg = await response.json();
            const wifiEb = ebCfg.wifi || {};
            const blacklist = wifiEb.mac_blacklist || [];

            tableBody.innerHTML = '';
            if (blacklist.length === 0) {
                tableBody.innerHTML = '<tr><td colspan="2" style="text-align: center; padding: 20px; color: var(--text-secondary);">No hay MACs bloqueadas</td></tr>';
                return;
            }

            blacklist.forEach(mac => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td style="padding: 12px; font-family: monospace;">${mac}</td>
                    <td style="padding: 12px; text-align: right;">
                        <button class="btn btn-red" onclick="removeWifiMac('${mac}')" style="padding: 5px 10px; font-size: 0.8rem;">Desbloquear</button>
                    </td>
                `;
                tableBody.appendChild(tr);
            });
        } else {
            tableBody.innerHTML = '<tr><td colspan="2" style="text-align: center; padding: 20px; color: var(--text-secondary);">No se encontraron MACs bloqueadas</td></tr>';
        }
    } catch (error) {
        tableBody.innerHTML = '<tr><td colspan="2" style="text-align: center; padding: 20px; color: var(--error);">Error al cargar MACs</td></tr>';
    }
}

async function addWifiMac() {
    const macField = document.getElementById('new-mac');
    if (!macField.value) {
        alert("Introduzca una dirección MAC");
        return;
    }

    try {
        const response = await fetch('/admin/ebtables', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'add_mac', params: { vlan_id: 'wifi', mac: macField.value } }),
            credentials: 'include'
        });
        const data = await response.json();
        if (data.success) {
            macField.value = '';
            // Asegurarse de que la blacklist esté habilitada para Wi-Fi
            await fetch('/admin/ebtables', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'enable_blacklist', params: { vlan_id: 'wifi' } }),
                credentials: 'include'
            });
            await loadWifiMacs();
        } else {
            alert("Error: " + (data.message || data.detail));
        }
    } catch (error) {
        alert("Error de conexión");
    }
}

async function removeWifiMac(mac) {
    if (!confirm(`¿Desbloquear la MAC ${mac}?`)) return;

    try {
        const response = await fetch('/admin/ebtables', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'remove_mac', params: { vlan_id: 'wifi', mac: mac } }),
            credentials: 'include'
        });
        const data = await response.json();
        if (data.success) {
            await loadWifiMacs();
        } else {
            alert("Error: " + (data.message || data.detail));
        }
    } catch (error) {
        alert("Error de conexión");
    }
}

async function loadPortalUsers() {
    const tableBody = document.getElementById('portal-users-table');
    if (!tableBody) return;
    tableBody.innerHTML = '<tr><td colspan="3" style="text-align: center; padding: 20px; color: var(--text-secondary);">Cargando usuarios...</td></tr>';

    try {
        const response = await fetch('/admin/wifi', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'list_portal_users', params: {} }),
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success && Array.isArray(data.message)) {
            if (data.message.length === 0) {
                tableBody.innerHTML = '<tr><td colspan="3" style="text-align: center; padding: 20px; color: var(--text-secondary); border-top: 1px solid rgba(255,255,255,0.05);">No hay usuarios registrados</td></tr>';
                return;
            }

            tableBody.innerHTML = '';
            data.message.forEach(user => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${user.username}</strong></td>
                    <td style="color: var(--text-secondary); font-size: 0.85rem;">${user.created_at}</td>
                    <td>
                        <button class="btn btn-red" onclick="removePortalUser('${user.username}')" style="padding: 5px 10px; font-size: 0.8rem;">Eliminar</button>
                    </td>
                `;
                tableBody.appendChild(tr);
            });
        } else {
            const errorMsg = data.message || (data.detail ? data.detail : 'Error desconocido');
            tableBody.innerHTML = '<tr><td colspan="3" style="text-align: center; padding: 20px; color: var(--error);">Error al cargar usuarios: ' + errorMsg + '</td></tr>';
        }
    } catch (error) {
        tableBody.innerHTML = '<tr><td colspan="3" style="text-align: center; padding: 20px; color: var(--error);">Error de conexión</td></tr>';
    }
}

async function addPortalUser() {
    const userField = document.getElementById('new-p-user');
    const passField = document.getElementById('new-p-pass');

    if (!userField.value || !passField.value) {
        alert("Por favor, rellene usuario y contraseña");
        return;
    }

    try {
        const response = await fetch('/admin/wifi', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                action: 'add_portal_user',
                params: { username: userField.value, password: passField.value }
            }),
            credentials: 'include'
        });
        const data = await response.json();
        if (data.success) {
            userField.value = '';
            passField.value = '';
            await loadPortalUsers();
        } else {
            const errorText = data.message || data.detail || "Error desconocido";
            alert("Error: " + errorText);
        }
    } catch (error) {
        alert("Error de conexión");
    }
}

async function removePortalUser(username) {
    if (!confirm(`¿Seguro que desea eliminar al usuario invitado '${username}'?`)) return;

    try {
        const response = await fetch('/admin/wifi', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'remove_portal_user', params: { username } }),
            credentials: 'include'
        });
        const data = await response.json();
        if (data.success) {
            await loadPortalUsers();
        }
    } catch (error) {
        alert("Error de conexión");
    }
}

async function saveConfig() {
    const msgDiv = document.getElementById('config-message');
    const btn = document.getElementById('btnSaveConfig');

    msgDiv.innerHTML = '<div class="loading">⏳ Guardando...</div>';
    btn.disabled = true;

    const params = {};
    const fieldIds = [
        'ssid', 'password', 'hw_mode', 'interface', 'security',
        'channel', 'ip_address', 'netmask', 'dhcp_start', 'dhcp_end',
        'portal_port'
    ];

    fieldIds.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            params[id] = (id === 'channel' || id === 'portal_port') ? parseInt(el.value) : el.value;
        }
    });

    if (document.getElementById('portal_enabled')) {
        params.portal_enabled = document.getElementById('portal_enabled').checked;
    }

    try {
        const response = await fetch('/admin/wifi', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'config', params }),
            credentials: 'include'
        });
        const data = await response.json();

        if (response.ok && data.success) {
            msgDiv.innerHTML = `
                <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid var(--success); padding: 15px; border-radius: 8px; color: var(--success); font-weight: 600;">
                    ✅ Configuración guardada correctamente. <br>
                    <span style="font-size: 0.9rem; font-weight: 400; opacity: 0.8;">Recuerde reiniciar el módulo para aplicar los cambios del AP y del Portal.</span>
                </div>
            `;
        } else {
            msgDiv.innerHTML = `
                <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid var(--error); padding: 15px; border-radius: 8px; color: #fca5a5;">
                    ❌ Error: ${data.message || data.detail || 'No se pudo guardar la configuración'}
                </div>
            `;
        }
    } catch (error) {
        msgDiv.innerHTML = '<div style="color: var(--error);">❌ Error de conexión</div>';
    } finally {
        btn.disabled = false;
    }
}

window.addEventListener('DOMContentLoaded', loadConfig);
