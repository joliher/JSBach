/* /web/modules/firewall/js/whitelist.js */

async function loadWhitelist() {
    const container = document.getElementById('whitelist-content');
    container.innerHTML = '<div class="loading">Cargando configuración...</div>';
    try {
        const resp = await fetch(`/admin/config/firewall/firewall.json?t=${Date.now()}`, { credentials: 'include', cache: 'no-cache' });
        const firewallConfig = await resp.json();

        if (Number(firewallConfig.status) !== 1) {
            container.innerHTML = '<div class="warning-box" style="text-align:center; padding:20px;"><h3>⚠️ Firewall Inactivo</h3><p>Active el firewall para configurar la whitelist.</p></div>';
            return;
        }
        renderWhitelistCards(firewallConfig);
    } catch (e) {
        container.innerHTML = '<div class="warning-box">⚠️ Error al cargar configuración.</div>';
    }
}

function renderWhitelistCards(firewallConfig) {
    const vlans = firewallConfig.vlans || {};
    const ids = Object.keys(vlans).sort((a, b) => parseInt(a) - parseInt(b));
    const container = document.getElementById('whitelist-content');

    let html = '';
    ids.forEach(id => {
        const v = vlans[id];
        const isSpecial = (id == 1 || id == 2);
        html += `
            <div class="vlan-card" style="border-left: 4px solid ${isSpecial ? '#dc2626' : '#10b981'}; background: rgba(15, 23, 42, 0.4); padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 15px;">
                    <div>
                        <h3 style="margin:0; color:var(--text-primary);">VLAN ${id}: ${v.name || ''}</h3>
                        <div style="font-size: 0.9rem; color: var(--text-secondary); margin-top: 4px;">IP: ${v.ip || 'N/A'}</div>
                    </div>
                    <div style="display: flex; gap: 8px;">
                        <span class="badge ${v.enabled ? 'badge-active' : 'badge-inactive'}">${v.enabled ? '✓ ACTIVA' : '✗ INACTIVA'}</span>
                        ${v.isolated ? '<span class="badge" style="background:rgba(245,158,11,0.1); color:var(--warning);">🔒 AISLADA</span>' : ''}
                        ${v.restricted ? '<span class="badge" style="background:rgba(245,158,11,0.1); color:var(--warning);">⛔ RESTRINGIDA</span>' : ''}
                    </div>
                </div>
                
                <div style="display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap;">
                    <button class="btn btn-small" style="background: ${v.restricted ? '#059669' : '#d97706'}" onclick="toggleRestriction(${id}, ${v.restricted})">${v.restricted ? '✓ DESRESTRINGIR' : '⛔ RESTRINGIR'}</button>
                    <button class="btn btn-small" style="background: ${v.isolated ? '#059669' : '#dc2626'}" onclick="toggleIsolation(${id}, ${v.isolated})" ${id == 1 ? 'disabled title="Auto-aislada"' : ''}>${v.isolated ? '🔓 UNISOLATE' : '🔒 ISOLATE'}</button>
                    ${!isSpecial ? `<button class="btn btn-small" style="background: ${v.whitelist_enabled ? '#dc2626' : '#059669'}" onclick="toggleWhitelist(${id}, ${v.whitelist_enabled})">${v.whitelist_enabled ? '🔓 DISABLE WHITELIST' : '🛡️ ENABLE WHITELIST'}</button>` : ''}
                </div>

                ${!isSpecial ? `
                    <div style="padding: 15px; background: rgba(0,0,0,0.2); border-radius: 6px; ${v.whitelist_enabled ? '' : 'opacity: 0.5; pointer-events: none;'}">
                        <strong style="font-size: 0.85rem; color: var(--text-secondary); display: block; margin-bottom: 10px;">REGLAS WHITELIST (IPS PERMITIDAS):</strong>
                        <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px;">
                            ${(v.whitelist || []).map(r => `
                                <span class="badge" style="background: rgba(255,255,255,0.05); display: flex; align-items: center; gap: 6px;">
                                    ${r} <span onclick="removeRule(${id}, '${r}')" style="cursor:pointer; color:var(--error); font-weight:bold;">×</span>
                                </span>
                            `).join('') || '<span style="color:#64748b; font-style:italic; font-size:0.85rem;">No hay reglas</span>'}
                        </div>
                        <div style="display: flex; gap: 8px;">
                            <input type="text" id="new-rule-${id}" style="flex:1;" placeholder="Ej: 8.8.8.8:53/udp">
                            <button class="btn btn-blue btn-small" onclick="addRule(${id})">Añadir</button>
                        </div>
                    </div>
                ` : '<div class="info-box" style="margin:0;">Las VLANs de administración tienen gestión especial de aislamiento.</div>'}
            </div>
        `;
    });
    container.innerHTML = html;
}

async function toggleWhitelist(vlanId, currentlyEnabled) {
    const action = currentlyEnabled ? 'disable_whitelist' : 'enable_whitelist';
    try {
        const resp = await fetch('/admin/firewall', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ action, params: { vlan_id: parseInt(vlanId) } })
        });
        if ((await resp.json()).success) loadWhitelist();
    } catch (e) { }
}

async function addRule(vlanId) {
    const input = document.getElementById(`new-rule-${vlanId}`);
    const rule = input.value.trim();
    if (!rule) return;
    try {
        const resp = await fetch('/admin/firewall', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ action: 'add_rule', params: { vlan_id: parseInt(vlanId), rule } })
        });
        const res = await resp.json();
        if (res.success) { input.value = ''; loadWhitelist(); }
        else showToast("❌ Error: " + (res.message || res.detail || "Error desconocido"));
    } catch (e) { alert('Error de conexión'); }
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
        if ((await resp.json()).success) loadWhitelist();
    } catch (e) { }
}

async function toggleIsolation(vlanId, isolated) {
    const action = isolated ? 'unisolate' : 'isolate';
    try {
        const resp = await fetch('/admin/firewall', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ action, params: { vlan_id: parseInt(vlanId) } })
        });
        if ((await resp.json()).success) loadWhitelist();
    } catch (e) { }
}

async function toggleRestriction(vlanId, restricted) {
    const action = restricted ? 'unrestrict' : 'restrict';
    try {
        const resp = await fetch('/admin/firewall', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ action, params: { vlan_id: parseInt(vlanId) } })
        });
        if ((await resp.json()).success) loadWhitelist();
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
        const res = await resp.json();
        if (res.success) setTimeout(loadWhitelist, 2000);
        else showToast("❌ Error: " + (res.message || res.detail || "Error desconocido"));
    } catch (e) { alert('Error de conexión'); }
}

window.addEventListener('DOMContentLoaded', loadWhitelist);
