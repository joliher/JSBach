let firewallConfig = {};

async function loadConfig() {
    try {
        const response = await fetch(`/config/firewall/firewall.json?t=${Date.now()}`, {
            credentials: 'include',
            cache: 'no-cache'
        });

    if (!response.ok) {
        throw new Error('No se pudo cargar la configuración');
    }

    firewallConfig = await response.json();

    // Verificar si el firewall está activo
    const status = Number(firewallConfig.status);
    if (status !== 1 || !firewallConfig.vlans || Object.keys(firewallConfig.vlans).length === 0) {
        document.getElementById('content').innerHTML = `
        <div class="warning-box" style="text-align: center; padding: 40px;">
        <h3 style="color: #856404; margin-top: 0;">⚠️ Firewall Inactivo</h3>
        <p style="font-size: 16px; margin: 20px 0;">
        Debes activar el FIREWALL antes de poder configurarlo.
        </p>
        <p style="color: #666;">
        Por favor, ve al menú principal y haz clic en <strong>START</strong> para iniciar el firewall.
        </p>
        </div>
        `;
        return;
    }

    renderVLANs();
} catch (error) {
    document.getElementById('content').innerHTML = `
    <div class="warning-box">
    ⚠️ Error al cargar configuración. Asegúrese de que el firewall esté iniciado (START).
    </div>
    `;
}
}

function renderVLANs() {
    const vlans = firewallConfig.vlans || {};
    let vlanIds = Object.keys(vlans);

    // Separar VLANs especiales (1 y 2) de las normales
    const specialVlanIds = vlanIds.filter(id => id == 1 || id == 2).sort((a, b) => parseInt(a) - parseInt(b));
    const normalVlanIds = vlanIds.filter(id => id != 1 && id != 2).sort((a, b) => parseInt(a) - parseInt(b));

    if (vlanIds.length === 0) {
        document.getElementById('content').innerHTML = `
        <div class="warning-box">
        ⚠️ No hay VLANs configuradas. Ejecute START en el firewall primero.
        </div>
        `;
        return;
    }

    let html = '';

    // Renderizar VLANs especiales (aislamiento + restricción)
    if (specialVlanIds.length > 0) {
        html += '<h3 style="color: #667eea; margin-top: 0;">🔐 VLANs Especiales (Aislamiento + Restricción)</h3>';

        specialVlanIds.forEach(vlanId => {
            const vlan = vlans[vlanId];
            const isolated = vlan.isolated || false;
            const restricted = vlan.restricted || false;
            const isVlan1 = (vlanId == 1);
            const isolationDisabled = isVlan1;

            html += `
            <div class="vlan-card" id="vlan-${vlanId}" style="border-left: 4px solid ${isVlan1 ? '#c0392b' : '#e74c3c'};">
            <div class="vlan-header">
            <div>
            <div class="vlan-title">
            VLAN ${vlanId}: ${vlan.name || 'Sin nombre'}
            <span class="status-badge ${isolated ? 'status-disabled' : 'status-enabled'}">
            ${isolated ? '🚫 AISLADA' : '✅ ACTIVA'}
            </span>
            ${restricted ? '<span class="status-badge status-warning" style="margin-left: 5px; background: #ff9800; color: white;">⛔ RESTRINGIDA</span>' : ''}
            </div>
            <div class="vlan-info">
            IP: ${vlan.ip || 'N/A'} | Estado: ${vlan.enabled ? 'Activa' : 'Inactiva'}
            </div>
            </div>
            <div style="display: flex; align-items: center; gap: 10px;">
            <button class="btn-add"
            onclick="toggleRestriction(${vlanId}, ${restricted})"
            style="${restricted ? 'background: #28a745;' : 'background: #ff9800;'}">
            ${restricted ? '✓ Desrestringir' : '⛔ Restringir'}
            </button>
            <button class="btn-add"
            onclick="${!isolationDisabled ? `toggleIsolation(${vlanId}, ${isolated})` : 'return false;'}"
            ${isolationDisabled ? 'disabled title="VLAN 1 se aísla automáticamente y no puede alternarse"' : ''}
            style="${isolated || isolationDisabled ? 'background: #28a745;' : 'background: #dc3545;'}; ${isolationDisabled ? 'opacity:0.6; cursor:not-allowed;' : ''}">
            ${isolationDisabled ? '🔓 Desaislar' : (isolated ? '🔓 Desaislar' : '🔒 Aislar')}
            </button>
            </div>
            </div>

            <div class="info-box" style="margin-top: 15px;">
            <strong>ℹ️ VLAN ${vlanId}:</strong>
            ${isVlan1
            ? 'Esta VLAN se aísla automáticamente en la primera inicialización. Bloquea tráfico ENTRANTE (desde fuera hacia VLAN 1), pero permite tráfico SALIENTE (desde VLAN 1 hacia fuera). Puedes restringir esta VLAN para bloquear acceso al router desde esta red.'
            : 'Esta VLAN puede ser aislada para bloquear nuevas conexiones, o restringida para bloquear acceso al router. Puedes combinar ambas configuraciones.'
        }
        </div>
        </div>
        `;
    });

if (normalVlanIds.length > 0) {
    html += '<h3 style="color: #667eea; margin-top: 30px;">🔥 VLANs Normales (Whitelist)</h3>';
}
}

// Renderizar VLANs normales (whitelist)
normalVlanIds.forEach(vlanId => {
    const vlan = vlans[vlanId];
    const enabled = vlan.whitelist_enabled || false;
    const isolated = vlan.isolated || false;
    const restricted = vlan.restricted || false;
    const whitelist = vlan.whitelist || [];

    html += `
    <div class="vlan-card" id="vlan-${vlanId}">
    <div class="vlan-header">
    <div>
    <div class="vlan-title">
    VLAN ${vlanId}: ${vlan.name || 'Sin nombre'}
    <span class="status-badge ${enabled ? 'status-enabled' : 'status-disabled'}">
    ${enabled ? '🔒 WHITELIST ACTIVA' : '🔓 WHITELIST INACTIVA'}
    </span>
    ${isolated ? '<span class="status-badge status-inactive" style="margin-left: 5px;">🚫 AISLADA</span>' : ''}
    ${restricted ? '<span class="status-badge status-warning" style="margin-left: 5px; background: #ff9800; color: white;">⛔ RESTRINGIDA</span>' : ''}
    </div>
    <div class="vlan-info">
    IP: ${vlan.ip || 'N/A'} | Estado: ${vlan.enabled ? 'Activa' : 'Inactiva'}
    </div>
    </div>
    <div style="display: flex; align-items: center; gap: 10px;">
    <button class="btn-add"
    onclick="toggleRestriction(${vlanId}, ${restricted})"
    style="${restricted ? 'background: #28a745;' : 'background: #ff9800;'}">
    ${restricted ? '✓ Desrestringir' : '⛔ Restringir'}
    </button>
    <button class="btn-add"
    onclick="toggleIsolation(${vlanId}, ${isolated})"
    style="${isolated ? 'background: #28a745;' : 'background: #dc3545;'}">
    ${isolated ? '🔓 Desaislar' : '🔒 Aislar'}
    </button>
    <div class="toggle-container">
    <span class="toggle-label ${enabled ? 'active' : ''}">
    ${enabled ? 'HABILITADA' : 'DESHABILITADA'}
    </span>
    <div class="toggle-switch ${enabled ? 'active' : ''}"
    onclick="toggleWhitelist(${vlanId})">
    </div>
    </div>
    </div>
    </div>

    <div class="whitelist-section ${enabled ? '' : 'disabled'}">
    <h4 style="margin-top: 0; color: #555;">📋 Reglas de Whitelist</h4>

    <div class="rules-list" id="rules-${vlanId}">
    ${whitelist.length === 0
    ? '<div class="no-rules">No hay reglas configuradas</div>'
    : whitelist.map((rule, idx) => `
    <div class="rule-item">
    <span class="rule-text">${rule}</span>
    <button class="btn-remove" onclick="removeRule(${vlanId}, '${rule}')">
    🗑️ Eliminar
    </button>
    </div>
    `).join('')
}
</div>

<div class="add-rule-form">
<input type="text"
id="newRule-${vlanId}"
placeholder="Ej: 8.8.8.8, :443, 8.8.8.8:53/udp"
onkeypress="if(event.key==='Enter') addRule(${vlanId})">
<button class="btn-add" onclick="addRule(${vlanId})">
➕ Agregar Regla
</button>
</div>
</div>

${enabled ? `
<div class="warning-box">
⚠️ <strong>Atención:</strong> Con whitelist activa, solo se permite tráfico a los destinos listados.
Todo lo demás será bloqueado (DROP).
</div>
` : ''}
</div>
`;
});

document.getElementById('content').innerHTML = html;
}

async function toggleWhitelist(vlanId) {
    const vlan = firewallConfig.vlans[vlanId];
    const currentState = vlan.whitelist_enabled || false;
    const action = currentState ? 'disable_whitelist' : 'enable_whitelist';

    try {
        const response = await fetch('/admin/firewall', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                action: action,
                params: {
                    vlan_id: parseInt(vlanId),
                    whitelist: vlan.whitelist || []
                }
            })
    });

    const result = await response.json();

    if (result.success) {
        firewallConfig.vlans[vlanId].whitelist_enabled = !currentState;
        renderVLANs();
    } else {
        alert('Error: ' + (result.message || 'No se pudo cambiar el estado'));
    }
} catch (error) {
    alert('Error de conexión al servidor');
}
}

async function addRule(vlanId) {
    const input = document.getElementById(`newRule-${vlanId}`);
    const rule = input.value.trim();

    if (!rule) {
        alert('Por favor ingrese una regla válida');
        return;
    }

    const ruleError = validateWhitelistRule(rule);
    if (ruleError) {
        alert(`Formato inválido: ${ruleError}\n\nEjemplos válidos:\n` +
        '- IP: 8.8.8.8\n' +
        '- IP/proto: 8.8.8.8/tcp\n' +
        '- IP:puerto: 192.168.1.1:80\n' +
        '- IP:puerto/proto: 8.8.8.8:53/udp\n' +
        '- :puerto: :443\n' +
        '- :puerto/proto: :22/tcp\n' +
        '- /tcp (cualquier IP y puerto con protocolo)');
        return;
    }

    // Validacion detallada ya realizada por validateWhitelistRule

    try {
        const response = await fetch('/admin/firewall', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                action: 'add_rule',
                params: {
                    vlan_id: parseInt(vlanId),
                    rule: rule
                }
            })
    });

    const result = await response.json();

    if (result.success) {
        if (!firewallConfig.vlans[vlanId].whitelist) {
            firewallConfig.vlans[vlanId].whitelist = [];
        }
        firewallConfig.vlans[vlanId].whitelist.push(rule);

        input.value = '';
        renderVLANs();
    } else {
        alert('Error: ' + (result.message || 'No se pudo agregar la regla'));
    }
} catch (error) {
    alert('Error de conexión al servidor');
}

function validateWhitelistRule(rule) {
    if (!rule || typeof rule !== 'string') return 'Regla vacía';

    const trimmed = rule.trim();
    if (!trimmed) return 'Regla vacía';

    let base = trimmed;
    let proto = null;
    if (trimmed.includes('/')) {
        const parts = trimmed.split('/');
        if (parts.length !== 2) return 'Formato inválido';
        base = parts[0].trim();
        proto = parts[1].trim().toLowerCase();
        if (proto !== 'tcp' && proto !== 'udp') return 'Protocolo inválido (use tcp o udp)';
    }

    if (base === '' && proto) {
        return null; // '/tcp' o '/udp'
    }

    if (base.startsWith(':')) {
        const portStr = base.slice(1).trim();
        if (!portStr) return 'Puerto requerido después de :';
        if (!/^[0-9]+$/.test(portStr)) return 'Puerto inválido';
        const port = parseInt(portStr, 10);
        if (port < 1 || port > 65535) return 'Puerto fuera de rango';
        return null;
    }

    let ipPart = base;
    let portPart = null;
    if (base.includes(':')) {
        const split = base.split(':');
        if (split.length !== 2) return 'Formato inválido';
        ipPart = split[0].trim();
        portPart = split[1].trim();
        if (!portPart) return 'Puerto requerido después de :';
        if (!/^[0-9]+$/.test(portPart)) return 'Puerto inválido';
        const port = parseInt(portPart, 10);
        if (port < 1 || port > 65535) return 'Puerto fuera de rango';
    }

    if (!ipPart) return 'IP requerida';

    if (isIPv4(ipPart)) return null;
    if (isIPv6(ipPart)) return 'IPv6 no soportado todavia';

    return 'IP inválida';
}

function isIPv4(ip) {
    const parts = ip.split('.');
    if (parts.length !== 4) return false;
    return parts.every(part => {
        if (!/^[0-9]+$/.test(part)) return false;
        const num = parseInt(part, 10);
        return num >= 0 && num <= 255;
    });
}

function isIPv6(ip) {
    return /^[0-9a-fA-F:]+$/.test(ip) && ip.includes(':');
}
}

async function removeRule(vlanId, rule) {
    if (!confirm(`¿Eliminar la regla "${rule}"?`)) {
        return;
    }


    try {
        const response = await fetch('/admin/firewall', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                action: 'remove_rule',
                params: {
                    vlan_id: parseInt(vlanId),
                    rule: rule
                }
            })
    });

    const result = await response.json();

    if (result.success) {
        const idx = firewallConfig.vlans[vlanId].whitelist.indexOf(rule);
        if (idx > -1) {
            firewallConfig.vlans[vlanId].whitelist.splice(idx, 1);
        }

        renderVLANs();
    } else {
        alert('Error: ' + (result.message || 'No se pudo eliminar la regla'));
    }
} catch (error) {
    alert('Error de conexión al servidor');
}
}

async function toggleIsolation(vlanId, currentlyIsolated) {
    if (parseInt(vlanId) === 1) {
        alert('VLAN 1 se aísla automáticamente al iniciar el firewall y no se puede alternar desde la web.');
        return;
    }
    const action = currentlyIsolated ? 'desaislar' : 'aislar';
    const actionText = currentlyIsolated ? 'desaislar' : 'aislar';

    if (!confirm(`¿Está seguro de ${actionText} la VLAN ${vlanId}?`)) {
        return;
    }

    try {
        const response = await fetch('/admin/firewall', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                action: action,
                params: {
                    vlan_id: parseInt(vlanId)
                }
            })
    });

    const result = await response.json();

    if (result.success) {
        firewallConfig.vlans[vlanId].isolated = !currentlyIsolated;
        renderVLANs();
        alert(result.message || `VLAN ${vlanId} ${actionText}da correctamente`);
    } else {
        alert('Error: ' + (result.message || `No se pudo ${actionText} la VLAN`));
    }
} catch (error) {
    alert('Error de conexión al servidor');
}
}

async function toggleRestriction(vlanId, currentlyRestricted) {
    const action = currentlyRestricted ? 'unrestrict' : 'restrict';
    const actionText = currentlyRestricted ? 'desrestringir' : 'restringir';

    const confirmMsg = currentlyRestricted
    ? `¿Desrestringir la VLAN ${vlanId}?\n\nEsto permitirá el acceso al router desde esta VLAN.`
    : `¿Restringir la VLAN ${vlanId}?\n\nEsto bloqueará el acceso al router desde esta VLAN.\nSe permitirá DHCP e ICMP (ping), pero se bloqueará el resto.`;

    if (!confirm(confirmMsg)) {
        return;
    }

    try {
        const response = await fetch('/admin/firewall', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                action: action,
                params: {
                    vlan_id: parseInt(vlanId)
                }
            })
    });

    const result = await response.json();

    if (result.success) {
        firewallConfig.vlans[vlanId].restricted = !currentlyRestricted;
        renderVLANs();
        alert(result.message || `VLAN ${vlanId} ${actionText}da correctamente`);
    } else {
        alert('Error: ' + (result.message || `No se pudo ${actionText} la VLAN`));
    }
} catch (error) {
    alert('Error de conexión al servidor');
}
}

async function resetDefaults() {
    const confirmMsg = `¿Restaurar FIREWALL a Valores Por Defecto?\n\n` +
    `VLAN 1: isolated=true, restricted=false\n` +
    `Otras VLANs: restricted=true\n\n` +
    `El firewall se reiniciará para aplicar los cambios.`;

    if (!confirm(confirmMsg)) {
        return;
    }

    try {
        const response = await fetch('/admin/firewall', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                action: 'reset_defaults',
                params: {}
            })
    });

    const result = await response.json();

    if (result.success) {
        alert('Firewall restaurado a valores por defecto y reiniciado correctamente.');
        // Recargar configuración
        setTimeout(() => {
            loadConfig();
        }, 2000);
    } else {
        alert('Error: ' + (result.message || 'No se pudo restaurar los valores por defecto'));
    }
} catch (error) {
    alert('Error de conexión al servidor');
}
}

window.addEventListener('DOMContentLoaded', () => {
    loadConfig();
});