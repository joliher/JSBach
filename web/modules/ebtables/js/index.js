/* /web/00-js/ebtables/index.js */

// --- GLOBAL STATE ---
let ebtablesConfig = {};
let vlansCache = [];
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

function showMessage(message, type = 'info') {
    const container = document.getElementById('message-container');
    if (!container) return;
    const alertClass = `alert alert-${type}`;
    const icon = type === 'success' ? '✅' : (type === 'danger' ? '❌' : 'ℹ️');
    container.innerHTML = `<div class="${alertClass}">${icon} ${escapeHtml(message)}</div>`;
    setTimeout(() => { container.innerHTML = ''; }, 5000);
}

// --- NAVIGATION ---
function switchSection(sectionId, btn) {
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    const target = document.getElementById('section-' + sectionId);
    if (target) target.classList.add('active');

    document.querySelectorAll('.sidebar button').forEach(b => b.classList.remove('selected'));
    if (btn) btn.classList.add('selected');

    sessionStorage.setItem("ebtablesSelectedSection", sectionId);
    if (btn) sessionStorage.setItem("ebtablesSelectedBtnId", btn.id);

    if (sectionId === 'config') loadConfigData();
    if (sectionId === 'status') refreshStatus();
}

// --- CORE ACTIONS ---
async function runEbtablesAction(action, btn) {
    switchSection('status', btn);
    const container = document.getElementById('status-container');
    container.innerHTML = `<div class="loading">⏳ Ejecutando acción: ${action.toUpperCase()}...</div>`;

    try {
        const resp = await fetch('/admin/ebtables', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action }),
            credentials: 'include'
        });
        const data = await resp.json();

        if (data.success) {
            container.innerHTML = `
                <div style="color: #667eea; font-weight: 600; margin-bottom: 10px;">✅ Acción completada con éxito</div>
                <div class="status-content">${escapeHtml(data.message)}</div>
            `;
        } else {
            container.innerHTML = `
                <div style="color: #e53e3e; font-weight: 600; margin-bottom: 10px;">❌ Error</div>
                <div class="status-content">${escapeHtml(data.message || 'Error desconocido')}</div>
            `;
        }
    } catch (error) {
        container.innerHTML = `<div style="color: #e53e3e;">❌ Error de conexión al servidor</div>`;
    }
}

async function refreshStatus() {
    const container = document.getElementById('status-container');
    container.innerHTML = '<div class="loading">Cargando estado de Ebtables...</div>';
    try {
        const resp = await fetch('/admin/ebtables', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'status' }),
            credentials: 'include'
        });
        const data = await resp.json();
        if (data.success) {
            container.innerHTML = `
                <div style="color: #667eea; font-weight: 600; margin-bottom: 10px;">✅ Estado obtenido correctamente</div>
                <div class="status-content">${escapeHtml(data.message)}</div>
            `;
        } else {
            container.innerHTML = `<div style="color: #e53e3e;">❌ Error: ${escapeHtml(data.message || 'Error desconocido')}</div>`;
        }
    } catch (e) { container.innerHTML = `<div style="color: #e53e3e;">❌ Error al obtener el estado</div>`; }
}

// --- DEPENDENCIES & STATUS ---
async function checkDependencies() {
    const btnStart = document.getElementById('btnStart');
    let wanReady = false, vlansReady = false, taggingReady = false;
    try {
        const statusResp = await fetch('/admin/status', { credentials: 'include' });
        const data = await statusResp.json();

        const wanS = data['wan'] || 'DESCONOCIDO';
        const vlansS = data['vlans'] || 'DESCONOCIDO';
        const taggingS = data['tagging'] || 'DESCONOCIDO';

        wanReady = (wanS === 'ACTIVO');
        vlansReady = (vlansS === 'ACTIVO');
        taggingReady = (taggingS === 'ACTIVO');

        document.getElementById('dep-wan').innerHTML = (wanReady ? '✅' : '❌') + ' WAN: ' + wanS;
        document.getElementById('dep-vlans').innerHTML = (vlansReady ? '✅' : '❌') + ' VLANs: ' + vlansS;
        document.getElementById('dep-tagging').innerHTML = (taggingReady ? '✅' : '❌') + ' Tagging: ' + taggingS;

        if (btnStart) btnStart.disabled = !(wanReady && vlansReady && taggingReady);
    } catch (e) { }
    clearTimeout(dependencyTimerId);
    dependencyTimerId = setTimeout(checkDependencies, 5000);
}

function fetchModuleStatus() {
    fetch('/admin/status', { credentials: 'include' })
        .then(resp => resp.json())
        .then(data => {
            const status = data['ebtables'] || 'DESCONOCIDO';
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

// --- PVLAN & WHITELIST CONFIG ---
async function loadConfigData() {
    const container = document.getElementById('vlan-container');
    try {
        // 1. Check module info
        const infoResp = await fetch('/admin/ebtables/info', { credentials: 'include' });
        const info = await infoResp.json();
        if (info.status !== 1) {
            container.innerHTML = '<div class="alert alert-warning">El módulo Ebtables debe estar ACTIVO para configurar aislamiento.</div>';
            return;
        }

        // 2. Fetch configs
        const [vlansResp, ebtResp] = await Promise.all([
            fetch('/admin/config/vlans/vlans.json?t=' + Date.now(), { credentials: 'include' }),
            fetch('/admin/config/ebtables/ebtables.json?t=' + Date.now(), { credentials: 'include' })
        ]);
        const vlansData = await vlansResp.json();
        ebtablesConfig = await ebtResp.json();
        vlansCache = vlansData.vlans || [];

        renderConfig();
    } catch (e) {
        container.innerHTML = '<div class="alert alert-danger">Error cargando configuración.</div>';
    }
}

function renderConfig() {
    const container = document.getElementById('vlan-container');
    if (!vlansCache.length) {
        container.innerHTML = '<div class="alert alert-info">No hay VLANs configuradas.</div>';
        return;
    }

    let html = `
        <table>
            <thead>
                <tr>
                    <th>VLAN</th>
                    <th>Estado PVLAN</th>
                    <th>MAC Whitelist (Admin)</th>
                    <th>Acciones</th>
                </tr>
            </thead>
            <tbody>
    `;

    vlansCache.forEach(vlan => {
        const vId = vlan.id.toString();
        const vConfig = (ebtablesConfig.vlans && ebtablesConfig.vlans[vId]) || {};
        const isIsolated = vConfig.isolated || false;
        const isVlan1 = (vId === '1');

        html += `
            <tr>
                <td><span class="vlan-id-badge">${vlan.id}</span> ${isVlan1 ? '<strong>(Admin)</strong>' : ''}</td>
                <td>
                    <span class="status-badge ${isIsolated ? 'status-inactive' : 'status-active'}">
                        ${isIsolated ? '🔒 Aislada' : '🔓 Normal'}
                    </span>
                </td>
                <td>
                    ${isVlan1 ? `
                        <div style="display:flex; flex-direction:column; gap:8px;">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <span class="status-badge ${vConfig.mac_whitelist_enabled !== false ? 'status-active' : 'status-inactive'}">
                                    ${vConfig.mac_whitelist_enabled !== false ? 'Habilitada' : 'Deshabilitada'}
                                </span>
                                <button class="btn btn-small" onclick="toggleWhitelist(${vConfig.mac_whitelist_enabled !== false})">⚙️</button>
                            </div>
                            <div style="display:flex; gap:4px;">
                                <input type="text" id="mac-input" placeholder="MAC..." style="flex:1; padding:4px; font-size:12px;">
                                <button class="btn btn-blue btn-small" onclick="addMac()">➕</button>
                            </div>
                            <div style="max-height:60px; overflow-y:auto; font-size:11px; color:#94a3b8;">
                                ${(vConfig.mac_whitelist || []).map(mac => `
                                    <div style="display:flex; justify-content:space-between; padding:2px 0;">
                                        <span>${mac}</span>
                                        <span style="cursor:pointer; color:#ef4444;" onclick="removeMac('${mac}')">×</span>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    ` : '<span style="color:#475569; font-style:italic;">N/A</span>'}
                </td>
                <td>
                    <button class="btn btn-small ${isIsolated ? 'btn-blue' : 'btn-red'}" onclick="togglePvlan(${vlan.id}, ${!isIsolated})">
                        ${isIsolated ? '🔓 Desactivar' : '🔒 Activar'}
                    </button>
                </td>
            </tr>
        `;
    });

    html += '</tbody></table>';
    container.innerHTML = html;
}

async function togglePvlan(vlanId, shouldIsolate) {
    const action = shouldIsolate ? 'isolate' : 'unisolate';
    if (!confirm(`¿${shouldIsolate ? 'Activar' : 'Desactivar'} PVLAN en VLAN ${vlanId}?`)) return;
    try {
        const resp = await fetch('/admin/ebtables', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
            body: JSON.stringify({ action, params: { vlan_id: vlanId.toString() } })
        });
        if ((await resp.json()).success) loadConfigData();
    } catch (e) { }
}

async function toggleWhitelist(currentlyEnabled) {
    const action = currentlyEnabled ? 'disable_whitelist' : 'enable_whitelist';
    try {
        const resp = await fetch('/admin/ebtables', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
            body: JSON.stringify({ action })
        });
        if ((await resp.json()).success) loadConfigData();
    } catch (e) { }
}

async function addMac() {
    const input = document.getElementById('mac-input');
    const mac = input.value.trim();
    if (!mac) return;
    try {
        const resp = await fetch('/admin/ebtables', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
            body: JSON.stringify({ action: 'add_mac', params: { mac } })
        });
        const data = await resp.json();
        if (data.success) { input.value = ''; loadConfigData(); }
        else showMessage(data.message, 'danger');
    } catch (e) { }
}

async function removeMac(mac) {
    if (!confirm(`¿Remover MAC ${mac}?`)) return;
    try {
        const resp = await fetch('/admin/ebtables', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
            body: JSON.stringify({ action: 'remove_mac', params: { mac } })
        });
        if ((await resp.json()).success) loadConfigData();
    } catch (e) { }
}

// --- INIT ---
window.addEventListener('DOMContentLoaded', () => {
    const savedSection = sessionStorage.getItem("ebtablesSelectedSection") || 'info';
    const savedBtnId = sessionStorage.getItem("ebtablesSelectedBtnId");
    const btn = document.getElementById(savedBtnId) || document.getElementById('btn' + savedSection.charAt(0).toUpperCase() + savedSection.slice(1));

    switchSection(savedSection, btn);
    fetchModuleStatus();
    checkDependencies();
});
