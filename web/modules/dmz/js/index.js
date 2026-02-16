/* /web/00-js/dmz/index.js */

// --- GLOBAL STATE ---
let currentDmzConfig = {};
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

function showResult(message, isSuccess, containerId = 'config-result') {
    const div = document.getElementById(containerId);
    if (!div) return;
    div.innerHTML = `<div class="${isSuccess ? 'success' : 'error'}">${escapeHtml(message)}</div>`;
    setTimeout(() => { div.innerHTML = ''; }, 5000);
}

// --- NAVIGATION ---
function switchSection(sectionId, btn) {
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    const target = document.getElementById('section-' + sectionId);
    if (target) target.classList.add('active');

    document.querySelectorAll('.sidebar button').forEach(b => b.classList.remove('selected'));
    if (btn) btn.classList.add('selected');

    sessionStorage.setItem("dmzSelectedSection", sectionId);
    if (btn) sessionStorage.setItem("dmzSelectedBtnId", btn.id);

    if (sectionId === 'destinations') loadDestinations();
    if (sectionId === 'config') checkFirewallStatus();
    if (sectionId === 'status') refreshStatus();
}

// --- CORE ACTIONS ---
async function runDmzAction(action, btn) {
    switchSection('status', btn);
    const container = document.getElementById('status-container');
    container.innerHTML = `<div class="loading">⏳ Ejecutando acción: ${action.toUpperCase()}...</div>`;

    try {
        const resp = await fetch('/admin/dmz', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action }),
            credentials: 'include'
        });
        const data = await resp.json();

        if (data.success) {
            container.innerHTML = `
                <div style="color: #3182ce; font-weight: 600; margin-bottom: 10px;">✅ Acción completada con éxito</div>
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
    container.innerHTML = '<div class="loading">Cargando estado de DMZ...</div>';
    try {
        const resp = await fetch('/admin/dmz', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'status' }),
            credentials: 'include'
        });
        const data = await resp.json();
        if (data.success) {
            container.innerHTML = `
                <div style="color: #3182ce; font-weight: 600; margin-bottom: 10px;">✅ Estado obtenido correctamente</div>
                <div class="status-content">${escapeHtml(data.message)}</div>
            `;
        } else {
            container.innerHTML = `<div style="color: #e53e3e;">❌ Error: ${escapeHtml(data.message || 'Error desconocido')}</div>`;
        }
    } catch (error) {
        container.innerHTML = `<div style="color: #e53e3e;">❌ Error al obtener el estado</div>`;
    }
}

// --- DEPENDENCIES & MODULE STATUS ---
async function checkDependencies() {
    const btnStart = document.getElementById('btnStart');
    let taggingReady = false, firewallReady = false;
    try {
        const statusResp = await fetch('/admin/status', { credentials: 'include' });
        const data = await statusResp.json();

        const taggingVal = data['tagging'] || 'DESCONOCIDO';
        const firewallVal = data['firewall'] || 'DESCONOCIDO';

        taggingReady = (taggingVal === 'ACTIVO');
        firewallReady = (firewallVal === 'ACTIVO');

        const tagDiv = document.getElementById('dep-tagging');
        const fwDiv = document.getElementById('dep-firewall');

        tagDiv.innerHTML = (taggingReady ? '✅' : '❌') + ' Tagging: ' + taggingVal;
        tagDiv.style.color = (taggingReady ? '#38a169' : '#e53e3e');

        fwDiv.innerHTML = (firewallReady ? '✅' : '❌') + ' Firewall: ' + firewallVal;
        fwDiv.style.color = (firewallReady ? '#38a169' : '#e53e3e');

        if (btnStart) btnStart.disabled = !(taggingReady && firewallReady);
    } catch (e) { }

    clearTimeout(dependencyTimerId);
    dependencyTimerId = setTimeout(checkDependencies, 5000);
}

function fetchModuleStatus() {
    fetch('/admin/status', { credentials: 'include' })
        .then(resp => resp.json())
        .then(data => {
            const status = data['dmz'] || 'DESCONOCIDO';
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

// --- DESTINATIONS ---
async function loadDestinations() {
    const tbody = document.querySelector("#destinationsTable tbody");
    tbody.innerHTML = '<tr><td colspan="5" class="loading">Cargando destinos...</td></tr>';
    try {
        const [dmzResp, wanResp, vlansResp] = await Promise.all([
            fetch('/admin/config/dmz/dmz.json', { credentials: 'include' }),
            fetch('/admin/config/wan/wan.json', { credentials: 'include' }),
            fetch('/admin/config/vlans/vlans.json', { credentials: 'include' })
        ]);
        currentDmzConfig = await dmzResp.json();
        const wanConfig = await wanResp.json();
        const vlansConfig = await vlansResp.json();

        document.getElementById('wan-iface').textContent = wanConfig.interface || 'N/A';
        const vlState = document.getElementById('vlans-state');
        vlState.innerHTML = vlansConfig.status === 1 ? '<span class="status-active">ACTIVAS</span>' : '<span class="status-inactive">INACTIVAS</span>';

        renderDestinationsTable();
    } catch (e) {
        tbody.innerHTML = '<tr><td colspan="5" class="error">Error cargando información</td></tr>';
    }
}

function renderDestinationsTable() {
    const tbody = document.querySelector("#destinationsTable tbody");
    tbody.innerHTML = "";
    const destinations = currentDmzConfig.destinations || [];

    if (destinations.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">No hay destinos configurados</td></tr>';
        return;
    }

    destinations.forEach(dest => {
        const isIsolated = dest.isolated === true;
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td><strong>${escapeHtml(dest.ip)}</strong></td>
            <td><code class="ip-code">${escapeHtml(String(dest.port))}</code></td>
            <td><span class="status-badge" style="background:rgba(59, 130, 246, 0.1); color:#3b82f6;">${escapeHtml(dest.protocol.toUpperCase())}</span></td>
            <td>
                <span class="status-badge ${isIsolated ? 'status-inactive' : 'status-active'}">
                    ${isIsolated ? '🔒 Aislado' : '🟢 Activo'}
                </span>
            </td>
            <td>
                <div style="display: flex; gap: 8px;">
                    <button class="btn btn-small" style="background: ${isIsolated ? '#059669' : '#dc2626'}" onclick="toggleIsolation('${dest.ip}', ${!isIsolated})">
                        ${isIsolated ? '🔓 Unisolate' : '🔒 Isolate'}
                    </button>
                    <button class="btn btn-red btn-small" onclick="deleteDestination('${dest.ip}', ${dest.port}, '${dest.protocol}')">🗑️</button>
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

async function toggleIsolation(ip, shouldIsolate) {
    const action = shouldIsolate ? 'isolate' : 'unisolate';
    if (!confirm(`¿Estás seguro de ${shouldIsolate ? 'aislar' : 'desaislar'} el host ${ip}?`)) return;
    try {
        const resp = await fetch('/admin/dmz', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
            body: JSON.stringify({ action, params: { ip } })
        });
        if ((await resp.json()).success) loadDestinations();
    } catch (e) { }
}

async function deleteDestination(ip, port, protocol) {
    if (!confirm(`¿Eliminar destino ${ip}:${port}/${protocol}?`)) return;
    try {
        const resp = await fetch('/admin/dmz', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
            body: JSON.stringify({ action: 'remove_destination', params: { ip, port, protocol } })
        });
        if ((await resp.json()).success) loadDestinations();
    } catch (e) { }
}

// --- CONFIG ---
async function checkFirewallStatus() {
    try {
        const resp = await fetch('/admin/config/firewall/firewall.json', { credentials: 'include' });
        const data = await resp.json();
        const isActive = data.status === 1;
        document.getElementById('firewall-warning').style.display = isActive ? 'none' : 'block';
        document.getElementById('submit-dmz').disabled = !isActive;
    } catch (e) { }
}

// --- INIT ---
window.addEventListener('DOMContentLoaded', () => {
    const savedSection = sessionStorage.getItem("dmzSelectedSection") || 'info';
    const savedBtnId = sessionStorage.getItem("dmzSelectedBtnId");
    const btn = document.getElementById(savedBtnId) || document.getElementById('btn' + savedSection.charAt(0).toUpperCase() + savedSection.slice(1));

    switchSection(savedSection, btn);
    fetchModuleStatus();
    checkDependencies();

    document.getElementById('dmz-form')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const ip = document.getElementById('dest-ip').value.trim();
        const port = parseInt(document.getElementById('dest-port').value);
        const protocol = document.getElementById('dest-protocol').value;

        if (ip.includes('/')) { showResult('❌ La IP no debe incluir máscara', false); return; }

        try {
            const resp = await fetch('/admin/dmz', {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
                body: JSON.stringify({ action: 'add_destination', params: { ip, port, protocol } })
            });
            const data = await resp.json();
            if (data.success) {
                e.target.reset();
                showResult('✅ Destino añadido', true);
                if (sessionStorage.getItem("dmzSelectedSection") === 'destinations') loadDestinations();
            } else showResult('❌ ' + data.message, false);
        } catch (e) { showResult('❌ Error de conexión', false); }
    });
});
