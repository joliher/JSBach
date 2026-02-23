/* /web/modules/expect/js/security.js */

let switchesCache = [];
let currentIp = null;
let securityState = {
    whitelist: [],
    mac_acl: {}, // Blacklist
    layers_info: []
};

// --- INITIALIZATION ---
document.addEventListener('DOMContentLoaded', async () => {
    await loadSwitches();

    document.getElementById('mac-switch').addEventListener('change', (e) => {
        currentIp = e.target.value;
        loadSecurityState();
    });
});

// --- LOAD DATA ---
async function loadSwitches() {
    const select = document.getElementById('mac-switch');
    try {
        const response = await fetch('/admin/expect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'list_switches' }),
            credentials: 'include'
        });
        const result = await response.json();
        const data = typeof result.message === 'string' ? JSON.parse(result.message) : result.message;
        switchesCache = data.switches || [];

        select.innerHTML = '<option value="" disabled selected>Seleccione un switch</option>';
        switchesCache.forEach(sw => {
            const opt = document.createElement('option');
            opt.value = sw.ip;
            opt.textContent = `${sw.name || 'Switch'} (${sw.ip})`;
            select.appendChild(opt);
        });
    } catch (e) {
        showToast("Error cargando lista de switches", "error");
    }
}

async function loadSecurityState() {
    if (!currentIp) return;

    try {
        const response = await fetch('/admin/expect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'get_state', params: { ip: currentIp } }),
            credentials: 'include'
        });
        const result = await response.json();

        if (result.success) {
            const rawMessage = typeof result.message === 'string' ? JSON.parse(result.message) : result.message;
            securityState = {
                whitelist: rawMessage.whitelist || [],
                mac_acl: rawMessage.mac_acl || {},
                layers_info: rawMessage.layers_info || [],
                ...rawMessage
            };
            updateUI();
        } else {
            console.error("API Error:", result.message);
            showToast("No se pudo obtener el estado: " + result.message, "error");
        }
    } catch (e) {
        console.error("Fetch/Parse Error:", e);
        showToast("Error de comunicación con el switch", "error");
    }
}

function updateUI() {
    const layersContainer = document.getElementById('layers-container');
    const modeDisplay = document.getElementById('mode-display');
    const syncBtn = document.getElementById('btn-sync-all');
    const layerHint = document.getElementById('layer-hint');

    if (syncBtn) syncBtn.disabled = !currentIp;
    layersContainer.innerHTML = "";

    if (!currentIp) {
        if (modeDisplay) modeDisplay.classList.add('hidden');
        if (layerHint) layerHint.classList.add('hidden');
        return;
    }

    if (layerHint) layerHint.classList.remove('hidden');
    if (modeDisplay) modeDisplay.classList.remove('hidden');

    // Render Dynamic Toggles
    const layers = securityState.layers_info || [];
    layers.forEach(layer => {
        const lid = layer.id;
        const enabled = securityState[`${lid}_enabled`];

        const group = document.createElement('div');
        group.className = 'control-group';
        group.innerHTML = `
            <label style="font-size: 0.75rem; opacity: 0.7; text-transform: uppercase;">${layer.name}:</label>
            <label class="toggle-switch">
                <input type="checkbox" id="${lid}Toggle" ${enabled ? 'checked' : ''} onchange="toggleLayer('${lid}')">
                <span class="slider"></span>
            </label>
        `;
        layersContainer.appendChild(group);
    });

    // Badge de estado general (heuristic)
    const wlEnabled = securityState.whitelist_enabled || false;
    const blEnabled = securityState.blacklist_enabled || false;
    const wlData = securityState.whitelist || [];

    if (wlEnabled && wlData.length > 0) {
        modeDisplay.textContent = '🛡️ VLAN 1: ZERO-TRUST';
        modeDisplay.className = 'mode-badge mode-whitelist';
    } else if (blEnabled) {
        modeDisplay.textContent = '🔓 GLOBAL: PROTECCIÓN ACTIVA';
        modeDisplay.className = 'mode-badge mode-blacklist';
    } else {
        modeDisplay.textContent = '⚠️ SEGURIDAD DESACTIVADA';
        modeDisplay.className = 'mode-badge';
        modeDisplay.style.background = 'rgba(255, 255, 255, 0.05)';
    }
    modeDisplay.classList.remove('hidden');

    // Whitelist Table
    const wTbody = document.querySelector("#whitelist-table tbody");
    wTbody.innerHTML = "";
    const wlList = securityState.whitelist || [];
    if (wlList.length === 0) {
        wTbody.innerHTML = '<tr><td colspan="2" style="text-align:center; color:var(--text-secondary);">Vacío</td></tr>';
    } else {
        wlList.forEach(mac => {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td><code>${mac}</code></td><td><button class="btn btn-red btn-small" onclick="removeFromWhitelist('${mac}')">🗑️</button></td>`;
            wTbody.appendChild(tr);
        });
    }

    // Blacklist Table
    const bTbody = document.querySelector("#blacklist-table tbody");
    bTbody.innerHTML = "";
    const bKeys = Object.keys(securityState.mac_acl || {});
    if (bKeys.length === 0) {
        bTbody.innerHTML = '<tr><td colspan="2" style="text-align:center; color:var(--text-secondary);">Vacío</td></tr>';
    } else {
        bKeys.forEach(mac => {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td><code>${mac}</code></td><td><button class="btn btn-blue btn-small" onclick="unisolateMac('${mac}')">🔓 Desaislar</button></td>`;
            bTbody.appendChild(tr);
        });
    }
}

// --- MAC DISCOVERY ---
async function refreshMacTable() {
    if (!currentIp) { alert("Seleccione un switch"); return; }

    const tbody = document.querySelector("#discovery-table tbody");
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;">Consultando switch...</td></tr>';

    try {
        const response = await fetch('/admin/expect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'mac_table', params: { ip: currentIp } }),
            credentials: 'include'
        });
        const result = await response.json();
        if (result.success) {
            const macs = parseMacTable(result.message);
            renderDiscoveryTable(macs);
        } else {
            tbody.innerHTML = `<tr><td colspan="4" style="color:var(--error); text-align:center;">${result.message}</td></tr>`;
        }
    } catch (e) {
        tbody.innerHTML = '<tr><td colspan="4" style="color:var(--error); text-align:center;">Error de red</td></tr>';
    }
}

function parseMacTable(text) {
    if (!text) return [];
    const lines = text.split(/[\r\n]+/).map(l => l.trim()).filter(l => l.length > 0);
    const macs = [];
    const macRegex = /([0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4}|([0-9a-f]{2}[:-]){5}[0-9a-f]{2})/i;

    lines.forEach(line => {
        const parts = line.split(/\s+/).filter(p => p.length > 0);
        if (parts.length < 3) return;
        let macFound = "";
        let macIdx = -1;
        for (let i = 0; i < parts.length; i++) {
            const match = parts[i].match(macRegex);
            if (match) { macIdx = i; macFound = match[0]; break; }
        }
        if (macIdx !== -1) {
            let vlan = '-', port = '-';
            // Simplified heuristic
            parts.forEach((p, idx) => {
                if (idx === macIdx) return;
                if (vlan === '-' && !isNaN(p) && parseInt(p) < 4095) vlan = p;
                else if (port === '-' && (p.match(/\b(gi|fa|te|eth|po|port|vlan)\S*\d/i) || p.match(/\d+\/\d+/))) port = p;
            });
            if (port.includes(':') && !port.includes('/')) return;
            if (port.match(/\d/)) macs.push({ mac: macFound, vlan, port });
        }
    });
    return macs;
}

function renderDiscoveryTable(macs) {
    const tbody = document.querySelector("#discovery-table tbody");
    tbody.innerHTML = "";
    if (macs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;">No se detectaron MACs.</td></tr>';
        return;
    }

    macs.forEach(item => {
        const normMac = normalizeMac(item.mac);
        const isIsolated = !!(securityState.mac_acl && securityState.mac_acl[normMac]);
        const isWhitelisted = (securityState.whitelist || []).includes(normMac);

        let statusHtml = '<span class="badge">Nueva</span>';
        if (isIsolated) statusHtml = '<span class="badge" style="background:rgba(239, 68, 68, 0.1); color:var(--error);">AISLADA</span>';
        else if (isWhitelisted) statusHtml = '<span class="badge" style="background:rgba(16, 185, 129, 0.1); color:var(--success);">AUTORIZADA</span>';

        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td><code>${item.mac}</code></td>
            <td>VLAN ${item.vlan} / ${item.port}</td>
            <td>${statusHtml}</td>
            <td>
                ${!isWhitelisted ? `<button class="btn btn-green btn-small" onclick="addToWhitelist('${normMac}')">✅ Whitelist</button>` : ''}
                ${!isIsolated ? `<button class="btn btn-red btn-small" onclick="isolateMac('${normMac}')">🚫 Aislar</button>` : `<button class="btn btn-blue btn-small" onclick="unisolateMac('${normMac}')">🔓 Desaislar</button>`}
            </td>
        `;
        tbody.appendChild(tr);
    });
}

// --- ACTIONS ---
async function toggleLayer(layer) {
    const toggle = document.getElementById(`${layer}Toggle`);
    const enabled = toggle.checked;

    showToast(`⏳ Sincronizando capa ${layer.toUpperCase()}...`, "info");
    const result = await callApi('security_toggle', { ip: currentIp, layer, enabled });

    if (result.success) {
        showToast(`Capa ${layer.toUpperCase()} ${enabled ? 'activada' : 'desactivada'}`, "success");
    } else {
        toggle.checked = !enabled;
    }
    loadSecurityState();
}

async function addToWhitelist(mac) {
    const result = await callApi('add_to_whitelist', { ip: currentIp, mac });
    if (result.success) showToast("MAC añadida localmente. Pulse SINCRONIZAR para aplicar.", "info");
    loadSecurityState();
}

async function removeFromWhitelist(mac) {
    if (!confirm(`¿Eliminar ${mac} de la whitelist?`)) return;
    const result = await callApi('remove_from_whitelist', { ip: currentIp, mac });
    if (result.success) showToast("MAC eliminada localmente. Pulse SINCRONIZAR para aplicar.", "info");
    loadSecurityState();
}

async function isolateMac(mac) {
    if (!confirm(`¿Bloquear acceso a ${mac}?`)) return;
    const result = await callApi('isolate', { ip: currentIp, mac });
    if (result.success) showToast("MAC aislada localmente. Pulse SINCRONIZAR para aplicar.", "info");
    loadSecurityState();
}

async function unisolateMac(mac) {
    const result = await callApi('unisolate', { ip: currentIp, mac });
    if (result.success) showToast("MAC desaislada localmente. Pulse SINCRONIZAR para aplicar.", "info");
    loadSecurityState();
}

async function applyUnifiedSecurity() {
    if (!confirm("Se enviará la configuración completa (Blacklist/Whitelist) al switch. ¿Continuar?\n\nEsto usará el método Zero-Disk (sin archivos temporales).")) return;
    const output = document.getElementById('output');
    document.getElementById('output-container').classList.remove('hidden');
    output.textContent = "⏳ Sincronizando comandos vía memoria (Zero-Disk Ready)...";
    output.style.color = 'var(--text-primary)';

    const result = await callApi('apply_whitelist', { ip: currentIp });
    if (result.success) {
        output.textContent = "✅ Sincronización Completada con éxito.\n\n" + (result.message || "El switch ha sido actualizado.");
        output.style.color = 'var(--success)';
        showToast("Switch sincronizado correctamente", "success");
    } else {
        output.textContent = "❌ Error en la sincronización:\n" + result.message;
        output.style.color = 'var(--error)';
    }
    loadSecurityState();
}

async function showAddManual(type) {
    const mac = prompt(`Ingrese la MAC para ${type === 'whitelist' ? 'autorizar' : 'aislar'}:`);
    if (!mac) return;
    if (type === 'whitelist') addToWhitelist(mac);
    else isolateMac(mac);
}

// --- HELPERS ---
async function callApi(action, params) {
    try {
        const resp = await fetch('/admin/expect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action, params }),
            credentials: 'include'
        });
        const data = await resp.json();
        if (!data.success) showToast(data.message, "error");
        return data;
    } catch (e) {
        showToast("Error de conexión", "error");
        return { success: false, message: "Error de red" };
    }
}

function normalizeMac(raw) {
    const cleaned = raw.replace(/[^0-9a-fA-F]/g, "").toLowerCase();
    if (cleaned.length !== 12) return raw.toLowerCase();
    return cleaned.match(/.{1,2}/g).join(":");
}
