/* /web/00-js/firewall/index.js */

// --- GLOBAL STATE ---
let firewallConfig = {};
let vlansConfig = {};
let lastStatus = '';
let pollInterval = 2000;
let unchangedCount = 0;
let statusTimerId = null;
let dependencyTimerId = null;

// --- UTILS ---
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
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
        if (proto !== 'tcp' && proto !== 'udp') return 'Protocolo inválido (tcp/udp)';
    }

    if (base === '' && proto) return null; // /tcp
    if (base.startsWith(':')) {
        const portStr = base.slice(1).trim();
        const port = parseInt(portStr, 10);
        if (isNaN(port) || port < 1 || port > 65535) return 'Puerto inválido';
        return null;
    }

    let ipPart = base;
    let portPart = null;
    if (base.includes(':')) {
        const split = base.split(':');
        if (split.length !== 2) return 'Formato inválido';
        ipPart = split[0].trim();
        portPart = split[1].trim();
        const port = parseInt(portPart, 10);
        if (isNaN(port) || port < 1 || port > 65535) return 'Puerto inválido';
    }
    if (!ipPart) return 'IP requerida';
    if (!isIPv4(ipPart)) return 'IP inválida';
    return null;
}

// --- NAVIGATION ---
function switchSection(sectionId, btn) {
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    const target = document.getElementById('section-' + sectionId);
    if (target) target.classList.add('active');

    document.querySelectorAll('.sidebar button').forEach(b => b.classList.remove('selected'));
    if (btn) btn.classList.add('selected');

    sessionStorage.setItem("firewallSelectedSection", sectionId);
    if (btn) sessionStorage.setItem("firewallSelectedBtnId", btn.id);

    if (sectionId === 'vlans') loadVlansView();
    if (sectionId === 'whitelist') loadWhitelistConfig();
    if (sectionId === 'status') refreshStatus();
}

// --- CORE ACTIONS ---
async function runFirewallAction(action, btn) {
    switchSection('status', btn);
    const container = document.getElementById('status-container');
    container.innerHTML = `<div class="loading">⏳ Ejecutando acción: ${action.toUpperCase()}...</div>`;

    try {
        const resp = await fetch('/admin/firewall', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action }),
            credentials: 'include'
        });
        const data = await resp.json();

        if (data.success) {
            container.innerHTML = `
                <div style="color: #059669; font-weight: 600; margin-bottom: 10px;">✅ Acción completada con éxito</div>
                <div style="border-top: 1px solid rgba(5, 150, 105, 0.2); padding-top: 10px; margin-top: 5px;">${escapeHtml(data.message)}</div>
            `;
        } else {
            container.innerHTML = `
                <div style="color: #dc2626; font-weight: 600; margin-bottom: 10px;">❌ Error</div>
                <div style="border-top: 1px solid rgba(220, 38, 38, 0.2); padding-top: 10px; margin-top: 5px; color: #fca5a5;">${escapeHtml(data.message || data.detail || 'Error desconocido')}</div>
            `;
        }
    } catch (error) {
        container.innerHTML = `<div style="color: #dc2626;">❌ Error de conexión al servidor</div>`;
    }
}

async function refreshStatus() {
    const container = document.getElementById('status-container');
    container.innerHTML = '<div class="loading">Cargando estado de Firewall...</div>';

    try {
        const resp = await fetch('/admin/firewall', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'status' }),
            credentials: 'include'
        });
        const data = await resp.json();
        if (data.success) {
            container.innerHTML = `
                <div style="color: #059669; font-weight: 600; margin-bottom: 10px;">✅ Estado obtenido correctamente</div>
                <div style="border-top: 1px solid rgba(5, 150, 105, 0.2); padding-top: 10px; margin-top: 5px;">${escapeHtml(data.message)}</div>
            `;
        } else {
            container.innerHTML = `<div style="color: #dc2626;">❌ Error: ${escapeHtml(data.message || data.detail || 'Error desconocido')}</div>`;
        }
    } catch (error) {
        container.innerHTML = `<div style="color: #dc2626;">❌ Error al obtener el estado</div>`;
    }
}

// --- DEPENDENCIES & MODULE STATUS ---
async function checkDependencies() {
    const btnStart = document.getElementById('btnStart');
    try {
        const statusResp = await fetch('/admin/status', { credentials: 'include' });
        const data = await statusResp.json();

        const vlansStatus = data['vlans'] || 'DESCONOCIDO';
        const taggingStatus = data['tagging'] || 'DESCONOCIDO';

        const vlansDiv = document.getElementById('dep-vlans');
        const taggingDiv = document.getElementById('dep-tagging');

        vlansDiv.innerHTML = (vlansStatus === 'ACTIVO' ? '✅' : '❌') + ' VLANs: ' + vlansStatus;
        vlansDiv.style.color = (vlansStatus === 'ACTIVO' ? '#059669' : '#dc2626');

        taggingDiv.innerHTML = (taggingStatus === 'ACTIVO' ? '✅' : '❌') + ' Tagging: ' + taggingStatus;
        taggingDiv.style.color = (taggingStatus === 'ACTIVO' ? '#059669' : '#dc2626');

        if (btnStart) btnStart.disabled = !(vlansStatus === 'ACTIVO' && taggingStatus === 'ACTIVO');
    } catch (e) { }

    clearTimeout(dependencyTimerId);
    dependencyTimerId = setTimeout(checkDependencies, 5000);
}

function fetchModuleStatus() {
    fetch('/admin/status', { credentials: 'include' })
        .then(resp => resp.json())
        .then(data => {
            const status = data['firewall'] || 'DESCONOCIDO';
            if (status !== lastStatus) {
                lastStatus = status;
                const statusBox = document.getElementById('module-status');
                statusBox.textContent = `Estado: ${status}`;
                statusBox.className = 'status-box ' + status.toLowerCase();
            }
            clearTimeout(statusTimerId);
            statusTimerId = setTimeout(fetchModuleStatus, 5000);
        });
}

// --- VLANS VIEW ---
async function loadVlansView() {
    const container = document.getElementById('vlans-content');
    container.innerHTML = '<div class="loading">Cargando VLANs...</div>';
    try {
        const [fwResp, vlansResp] = await Promise.all([
            fetch('/admin/config/firewall/firewall.json', { credentials: 'include' }),
            fetch('/admin/config/vlans/vlans.json', { credentials: 'include' })
        ]);
        firewallConfig = await fwResp.json();
        vlansConfig = await vlansResp.json();
        renderVlansTable();
    } catch (e) {
        container.innerHTML = '<div class="warning-box">⚠️ Error al cargar datos. Inicie el firewall primero.</div>';
    }
}

function renderVlansTable() {
    const fwVlans = firewallConfig.vlans || {};
    const systemVlans = vlansConfig.vlans || [];
    const container = document.getElementById('vlans-content');
    if (!container) return;

    if (systemVlans.length === 0) {
        container.innerHTML = '<div class="info-box">No hay VLANs configuradas.</div>';
        return;
    }

    let html = '<table><thead><tr><th>ID</th><th>Nombre</th><th>IP/Red</th><th>Seguridad</th></tr></thead><tbody>';
    systemVlans.sort((a, b) => parseInt(a.id) - parseInt(b.id)).forEach(vlan => {
        const id = vlan.id;
        const v = fwVlans[String(id)] || {};
        const isProtected = (id == 1 || id == 2);

        html += `
            <tr>
                <td><span class="vlan-id ${isProtected ? 'protected' : ''}">${id}</span></td>
                <td><strong>${escapeHtml(vlan.name || 'Sin nombre')}</strong></td>
                <td><code class="ip-code">${escapeHtml(vlan.ip_network || 'N/A')}</code></td>
                <td>
                    <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                        <span class="status-badge ${v.restricted ? 'status-active' : 'status-inactive'}">${v.restricted ? '✓ Restricted' : '✗ Open'}</span>
                        <span class="status-badge ${v.isolated ? 'status-inactive' : 'status-active'}">${v.isolated ? '🔒 Isolated' : '🔓 Public'}</span>
                        <button class="btn btn-small" onclick="switchSection('whitelist', null); loadWhitelistConfig();" style="background:#475569; color:white;">⚙️ Config</button>
                    </div>
                </td>
            </tr>
        `;
    });
    html += '</tbody></table>';
    container.innerHTML = html;
}

// --- WHITELIST CONFIG ---
async function loadWhitelistConfig() {
    const container = document.getElementById('whitelist-content');
    container.innerHTML = '<div class="loading">Cargando configuración...</div>';
    try {
        const resp = await fetch(`/admin/config/firewall/firewall.json?t=${Date.now()}`, { credentials: 'include', cache: 'no-cache' });
        firewallConfig = await resp.json();
        if (Number(firewallConfig.status) !== 1) {
            container.innerHTML = '<div class="warning-box" style="text-align:center; padding:20px;"><h3>⚠️ Firewall Inactivo</h3><p>Active el firewall para configurar la whitelist.</p></div>';
            return;
        }
        renderWhitelistCards();
    } catch (e) {
        container.innerHTML = '<div class="warning-box">⚠️ Error al cargar configuración.</div>';
    }
}

function renderWhitelistCards() {
    const vlans = firewallConfig.vlans || {};
    const ids = Object.keys(vlans).sort((a, b) => parseInt(a) - parseInt(b));
    const container = document.getElementById('whitelist-content');

    let html = '';
    ids.forEach(id => {
        const v = vlans[id];
        const isSpecial = (id == 1 || id == 2);
        html += `
            <div class="vlan-card" border-left: 4px solid ${isSpecial ? '#dc3545' : '#10b981'};">
                <div class="vlan-header">
                    <div>
                        <div class="vlan-title">VLAN ${id}: ${v.name || ''} 
                            <span class="status-badge ${v.enabled ? 'status-enabled' : 'status-disabled'}">${v.enabled ? '✓ Activa' : '✗ Inactiva'}</span>
                            ${v.isolated ? '<span class="status-badge status-warning">🔒 Aislada</span>' : ''}
                            ${v.restricted ? '<span class="status-badge status-warning">⛔ Restringida</span>' : ''}
                        </div>
                        <div class="vlan-info">IP: ${v.ip || 'N/A'}</div>
                    </div>
                </div>
                <div style="display: flex; gap: 10px; margin-bottom: 20px;">
                    <button class="btn-add" style="background: ${v.restricted ? '#059669' : '#d97706'}" onclick="toggleRestriction(${id}, ${v.restricted})">${v.restricted ? '✓ Desrestringir' : '⛔ Restringir'}</button>
                    <button class="btn-add" style="background: ${v.isolated ? '#059669' : '#dc2626'}" onclick="toggleIsolation(${id}, ${v.isolated})" ${id == 1 ? 'disabled title="Auto-aislada"' : ''}>${v.isolated ? '🔓 Unisolate' : '🔒 Isolate'}</button>
                    ${!isSpecial ? `<button class="btn-add" style="background: ${v.whitelist_enabled ? '#dc2626' : '#059669'}" onclick="toggleWhitelist(${id}, ${v.whitelist_enabled})">${v.whitelist_enabled ? '🔓 Disable Whitelist' : '🛡️ Enable Whitelist'}</button>` : ''}
                </div>
                ${!isSpecial ? `
                    <div class="rules-section" style="${v.whitelist_enabled ? '' : 'opacity: 0.5; pointer-events: none;'}">
                        <strong>Reglas Whitelist:</strong>
                        <div style="margin: 10px 0;">
                            ${(v.whitelist || []).map(r => `<span class="rule-item" style="background:#f3f4f6; padding:4px 8px; border-radius:4px; margin-right:5px; font-size:12px;">${r} <button onclick="removeRule(${id}, '${r}')" style="border:none; color:red; cursor:pointer;">×</button></span>`).join('') || 'Sin reglas'}
                        </div>
                        <div style="display:flex; gap:5px;">
                            <input type="text" id="new-rule-${id}" style="padding:6px; border:1px solid #ddd; border-radius:4px; flex-grow:1;" placeholder="Ej: 8.8.8.8:53/udp">
                            <button class="btn-add" style="padding:4px 10px;" onclick="addRule(${id})">添加</button>
                        </div>
                    </div>
                ` : '<div class="info-box">Las VLANs 1 y 2 tienen gestión especial de aislamiento.</div>'}
            </div>
        `;
    });
    container.innerHTML = html;
}

// --- ACTIONS FOR WHITELIST CONFIG ---
async function toggleWhitelist(vlanId, currentlyEnabled) {
    const action = currentlyEnabled ? 'disable_whitelist' : 'enable_whitelist';
    try {
        const resp = await fetch('/admin/firewall', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ action, params: { vlan_id: parseInt(vlanId), whitelist: firewallConfig.vlans[vlanId].whitelist || [] } })
        });
        const result = await resp.json();
        if (result.success) loadWhitelistConfig();
        else alert(result.message);
    } catch (e) { alert('Error de conexión'); }
}

async function addRule(vlanId) {
    const input = document.getElementById(`new-rule-${vlanId}`);
    const rule = input.value.trim();
    const err = validateWhitelistRule(rule);
    if (err) { alert(err); return; }

    try {
        const resp = await fetch('/admin/firewall', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ action: 'add_rule', params: { vlan_id: parseInt(vlanId), rule } })
        });
        if ((await resp.json()).success) { input.value = ''; loadWhitelistConfig(); }
    } catch (e) { }
}

async function removeRule(vlanId, rule) {
    if (!confirm('¿Eliminar regla?')) return;
    try {
        const resp = await fetch('/admin/firewall', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ action: 'remove_rule', params: { vlan_id: parseInt(vlanId), rule } })
        });
        if ((await resp.json()).success) loadWhitelistConfig();
    } catch (e) { }
}

async function toggleIsolation(vlanId, isolated) {
    const action = isolated ? 'unisolate' : 'isolate';
    if (!confirm(`¿${action} VLAN ${vlanId}?`)) return;
    try {
        const resp = await fetch('/admin/firewall', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ action, params: { vlan_id: parseInt(vlanId) } })
        });
        if ((await resp.json()).success) loadWhitelistConfig();
    } catch (e) { }
}

async function toggleRestriction(vlanId, restricted) {
    const action = restricted ? 'unrestrict' : 'restrict';
    if (!confirm(`¿${action} acceso al router para VLAN ${vlanId}?`)) return;
    try {
        const resp = await fetch('/admin/firewall', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ action, params: { vlan_id: parseInt(vlanId) } })
        });
        if ((await resp.json()).success) loadWhitelistConfig();
    } catch (e) { }
}

async function resetDefaults() {
    if (!confirm('¿Restablecer firewall a valores por defecto?')) return;
    try {
        const resp = await fetch('/admin/firewall', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ action: 'reset_defaults', params: {} })
        });
        if ((await resp.json()).success) setTimeout(loadWhitelistConfig, 2000);
    } catch (e) { }
}

// --- INIT ---
window.addEventListener('DOMContentLoaded', () => {
    const savedSection = sessionStorage.getItem("firewallSelectedSection") || 'info';
    const savedBtnId = sessionStorage.getItem("firewallSelectedBtnId");
    const btn = document.getElementById(savedBtnId) || document.getElementById('btn' + savedSection.charAt(0).toUpperCase() + savedSection.slice(1));

    switchSection(savedSection, btn);
    fetchModuleStatus();
    checkDependencies();
});
