/* /web/00-js/expect/index.js */

// --- GLOBAL STATE ---
let switchesCache = {};
let profileData = null;
let globalParams = {};
let interfaceParams = {};
let interfaceBlockId = 0;

// --- UTILS ---
function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function parseSwitchesMessage(message) {
    if (!message) return { switches: [] };
    if (typeof message === 'object') return message;
    if (typeof message === 'string') {
        const trimmed = message.trim();
        if (!trimmed) return { switches: [] };
        if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
            try {
                const parsed = JSON.parse(trimmed);
                return Array.isArray(parsed) ? { switches: parsed } : parsed;
            } catch (e) { return { switches: [] }; }
        }
    }
    return { switches: [] };
}

function showResult(section, message, isError = false) {
    const result = document.getElementById(`result-${section}`) || document.getElementById('output');
    if (!result) return;
    result.textContent = message;
    result.style.display = 'block';
    result.style.color = isError ? '#ff5555' : '#00ff00';
    if (section === 'switches' || section === 'macs') {
        result.className = isError ? 'result error' : 'result success';
    }
}

// --- NAVIGATION ---
function switchSection(sectionId, btn) {
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    const target = document.getElementById('section-' + sectionId);
    if (target) target.classList.add('active');

    document.querySelectorAll('.sidebar button').forEach(b => b.classList.remove('selected'));
    if (btn) btn.classList.add('selected');

    sessionStorage.setItem("expectSelectedSection", sectionId);

    if (sectionId === 'config') loadSwitchesForConfig();
    if (sectionId === 'switches') loadSwitchesForTable();
    if (sectionId === 'macs') loadSwitchesForMacs();
}

// --- CONFIG MODULE ---
async function loadSwitchesForConfig() {
    const targetIpSelect = document.getElementById('target-ip');
    if (!targetIpSelect) return;
    try {
        const response = await fetch('/admin/expect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'list_switches' }),
            credentials: 'include'
        });
        const result = await response.json();
        const data = parseSwitchesMessage(result.message);
        const switches = data.switches || [];
        switchesCache = {};
        switches.forEach(sw => { if (sw && sw.ip) switchesCache[sw.ip] = sw; });
        const savedIp = sessionStorage.getItem('expectSelectedIp');
        targetIpSelect.innerHTML = '<option value="" disabled selected>Seleccione un switch</option>';
        switches.forEach(sw => {
            const option = document.createElement('option');
            option.value = sw.ip;
            option.textContent = sw.name ? `${sw.name} (${sw.ip})` : sw.ip;
            if (savedIp === sw.ip) option.selected = true;
            targetIpSelect.appendChild(option);
        });
        if (!savedIp && switches[0]) targetIpSelect.value = switches[0].ip;
        updateAuthFeedback(targetIpSelect.value);
        await loadProfileParams();
    } catch (e) { console.error(e); }
}

async function loadProfileParams() {
    const ip = document.getElementById('target-ip')?.value;
    const profileId = switchesCache[ip]?.profile;
    if (!profileId) return;
    try {
        const response = await fetch(`/admin/expect/profiles/${profileId}`, { credentials: 'include' });
        profileData = await response.json();
        globalParams = {}; interfaceParams = {};
        for (let [key, val] of Object.entries(profileData.parameters)) {
            if (val.context === 'global') globalParams[key] = val;
            else interfaceParams[key] = val;
        }
        document.getElementById('global-config-container').innerHTML = '';
        document.getElementById('interface-config-container').innerHTML = '';
        if (profileData.auth_required !== undefined) document.getElementById('auth_required').checked = profileData.auth_required;
        toggleAuthWarning();
    } catch (e) { console.error(e); }
}

function updateAuthFeedback(ip) {
    const sw = switchesCache[ip];
    document.getElementById('auth-feedback-user').textContent = sw?.user || '-';
    // Use hidden input or just display mask
    document.getElementById('auth-feedback-profile').textContent = sw?.profile || '-';
}

function toggleAuthWarning() {
    const show = document.getElementById('auth_required').checked;
    document.getElementById('auth-warning-box').classList.toggle('hidden', !show);
    document.getElementById('auth-feedback').classList.toggle('hidden', !show);
}

// Full version of addParamRow and serializeActions would go here...
// I will include the core logic for adding rows

function addParamRow(context, key, blockId = null, containerOverride = null) {
    const params = context === 'global' ? globalParams : interfaceParams;
    let mainContainer = context === 'global' ? document.getElementById('global-config-container') : document.getElementById(blockId).querySelector('.interface-params-list');
    const container = containerOverride || mainContainer;
    const wrapper = document.createElement('div');
    wrapper.className = 'param-wrapper';
    const row = document.createElement('div');
    row.className = 'config-row';
    const paramDef = params[key];
    let inputHtml = `<input type="text" placeholder="Valor para ${key}" required style="flex: 1;">`;
    if (paramDef?.validation?.startsWith('enum:')) {
        const options = paramDef.validation.replace('enum:', '').split(',');
        inputHtml = `<select required style="flex: 1; padding: 10px;">${options.map(o => `<option value="${o}">${o}</option>`).join('')}</select>`;
    }
    row.innerHTML = `<div class="param-label" data-key="${key}">${key.toUpperCase()}</div>${inputHtml}<button type="button" class="btn-icon" onclick="this.closest('.param-wrapper').remove()">🗑️</button>`;
    wrapper.appendChild(row);
    container.appendChild(wrapper);
    if (context === 'global') document.getElementById('global-config-container').style.display = 'block';
}

function showParamMenu(btn, context, blockId = null) {
    const menu = btn.nextElementSibling;
    const params = context === 'global' ? globalParams : interfaceParams;
    let html = `<div class="menu-header">Añadir Parámetro</div>`;
    Object.keys(params).forEach(k => {
        html += `<button type="button" onclick="addParamRow('${context}', '${k}', ${blockId ? `'${blockId}'` : 'null'})">${k.toUpperCase()}</button>`;
    });
    menu.innerHTML = html;
    menu.style.display = 'block';
}

function addInterfaceBlock() {
    const container = document.getElementById('interface-config-container');
    const blockId = `interface-block-${interfaceBlockId++}`;
    const div = document.createElement('div');
    div.className = 'config-block';
    div.id = blockId;
    div.innerHTML = `
        <div class="config-row" style="grid-template-columns: 100px 1fr auto;">
            <div class="param-label" style="background: #f1f2f6; width: 100px;">PUERTOS</div>
            <input type="text" class="port-input" placeholder="Ej: 1-4" required>
            <button type="button" class="btn-icon" onclick="this.closest('.config-block').remove()">🗑️</button>
        </div>
        <div class="interface-params-list"></div>
        <div class="add-param-container" style="margin-top: 10px;">
            <button type="button" class="btn btn-blue btn-small" onclick="showParamMenu(this, 'interface', '${blockId}')">➕ Parámetro</button>
            <div class="param-menu"></div>
        </div>
    `;
    container.appendChild(div);
}

// --- SWITCHES TABLE ---
async function loadSwitchesForTable() {
    const tbody = document.querySelector("#switches-table tbody");
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="6" class="loading">Cargando switches...</td></tr>';
    try {
        const response = await fetch('/admin/expect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'list_switches' }),
            credentials: 'include'
        });
        const result = await response.json();
        if (!result.success) {
            tbody.innerHTML = `<tr><td colspan="6" class="error">Error: ${escapeHtml(result.message)}</td></tr>`;
            return;
        }
        const data = parseSwitchesMessage(result.message);
        const switches = data.switches || (Array.isArray(data) ? data : []);
        switchesCache = {};
        switches.forEach(sw => { if (sw && sw.ip) switchesCache[sw.ip] = sw; });
        tbody.innerHTML = "";
        if (switches.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #91a7ff;">No hay switches registrados</td></tr>';
            return;
        }
        switches.forEach(sw => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td><b>${escapeHtml(sw.name || '')}</b></td>
                <td><code>${escapeHtml(sw.ip || '')}</code></td>
                <td>${escapeHtml(sw.user || '-')}</td>
                <td><span class="badge">${escapeHtml(sw.profile || '')}</span></td>
                <td><span class="badge" style="background: #748ffc;">${escapeHtml(sw.protocol || 'telnet')}</span></td>
                <td>
                    <button class="btn btn-blue btn-small" onclick="editSwitch('${sw.ip}')" title="Editar">✏️</button>
                    <button class="btn btn-red btn-small" onclick="deleteSwitch('${sw.ip}')" title="Eliminar">🗑️</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.error(e);
        tbody.innerHTML = '<tr><td colspan="5" class="error">Error de red o de proceso</td></tr>';
    }
}

async function saveSwitch(e) {
    if (e) e.preventDefault();
    const name = document.getElementById('sw-name').value;
    const ip = document.getElementById('sw-ip').value;
    const user = document.getElementById('sw-user').value;
    const pass = document.getElementById('sw-pass').value;
    const noPass = document.getElementById('sw-no-pass').checked;
    const profile = document.getElementById('sw-profile').value;
    const protocol = document.getElementById('sw-protocol').value;
    const max_ports = parseInt(document.getElementById('sw-max-ports').value) || 24;
    const originalIp = document.getElementById('sw-original-ip').value;

    const action = originalIp ? 'update_switch' : 'add_switch';
    const params = { name, ip, user, profile, protocol, max_ports };
    if (originalIp) params.original_ip = originalIp;
    if (noPass) params.password = "";
    else if (pass) params.password = pass;

    showResult('switches', '⏳ Guardando...', false);
    try {
        const response = await fetch('/admin/expect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action, params }),
            credentials: 'include'
        });
        const result = await response.json();
        if (result.success) {
            showResult('switches', '✅ Switch guardado correctamente', false);
            document.getElementById('switch-form').reset();
            loadSwitchesForTable();
        } else {
            showResult('switches', '❌ Error: ' + result.message, true);
        }
    } catch (e) {
        showResult('switches', '❌ Error de red', true);
    }
}

async function deleteSwitch(ip) {
    if (!confirm(`¿Eliminar switch ${ip}?`)) return;
    showResult('switches', '⏳ Eliminando...', false);
    try {
        const response = await fetch('/admin/expect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'remove_switch', params: { ip } }),
            credentials: 'include'
        });
        const result = await response.json();
        if (result.success) {
            showResult('switches', '✅ Switch eliminado', false);
            loadSwitchesForTable();
        } else {
            showResult('switches', '❌ Error: ' + result.message, true);
        }
    } catch (e) {
        showResult('switches', '❌ Error de red', true);
    }
}

function editSwitch(ip) {
    const sw = switchesCache[ip];
    if (!sw) return;
    document.getElementById('sw-original-ip').value = sw.ip || '';
    document.getElementById('sw-name').value = sw.name || '';
    document.getElementById('sw-ip').value = sw.ip || '';
    document.getElementById('sw-user').value = sw.user || '';
    document.getElementById('sw-profile').value = sw.profile || 'cisco_ios';
    document.getElementById('sw-protocol').value = sw.protocol || 'telnet';
    document.getElementById('sw-max-ports').value = sw.max_ports || 24;
    document.getElementById('sw-pass').value = '';
    document.getElementById('sw-no-pass').checked = (sw.password === "");
}

// --- MAC TABLE HELPERS ---
function parseMacTable(text) {
    if (!text) return [];
    // Split by any combination of \r and \n to be robust and trim each line
    const lines = text.split(/[\r\n]+/).map(l => l.trim()).filter(l => l.length > 0);
    const macs = [];
    const macRegex = /([0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4}|([0-9a-f]{2}[:-]){5}[0-9a-f]{2})/i;

    lines.forEach(line => {
        const parts = line.split(/\s+/).filter(p => p.length > 0);
        if (parts.length < 3) return;

        let macIdx = -1;
        let macFound = "";

        for (let i = 0; i < parts.length; i++) {
            const match = parts[i].match(macRegex);
            if (match) {
                macIdx = i;
                macFound = match[0]; // Cleanly capture only the MAC
                break;
            }
        }

        if (macIdx !== -1) {
            let vlan = '-';
            let port = '-';

            // Positional Logic for common formats
            if (macIdx === 0 && parts.length >= 3) {
                // TP-Link Style: MAC(0) VLAN(1) Port(2) Type(3) Aging(4)
                vlan = parts[1];
                port = parts[2];
            } else if (macIdx === 1 && parts.length >= 4) {
                // Cisco Style: VLAN(0) MAC(1) Type(2) Port(3)
                vlan = parts[0];
                port = parts[3];
            } else {
                // Fallback heuristic categorization
                for (let i = 0; i < parts.length; i++) {
                    if (i === macIdx) continue;
                    const p = parts[i];
                    if (vlan === '-' && !isNaN(p) && parseInt(p) < 4095) vlan = p;
                    else if (port === '-' && (p.match(/\b(gi|fa|te|eth|po|port|vlan)\S*\d/i) || p.match(/\d+\/\d+/))) port = p;
                }
            }

            // Cleanup fields from any remaining control characters
            vlan = vlan.replace(/[^\w.-]/g, '');
            port = port.replace(/[^\w/.-]/g, '');

            // Noise reduction: Filter out entries where port looks like a timestamp/log
            if (port.includes(':') && !port.includes('/')) return; // Probably time 00:00:00
            if (port.includes(',') || port.includes('[')) return; // Probably log message
            if (!port.match(/\d/)) return; // Port should usually have some number

            macs.push({ mac: macFound, vlan, port });
        }
    });
    return macs;
}

async function isolateMac(ip, mac) {
    if (!confirm(`¿Bloquear MAC ${mac} en el switch ${ip}?`)) return;
    showResult('macs', `⏳ Aislando ${mac}...`, false);
    try {
        const response = await fetch('/admin/expect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'isolate', params: { ip, mac } }),
            credentials: 'include'
        });
        const result = await response.json();
        if (result.success) {
            showResult('macs', `✅ MAC ${mac} bloqueada correctamente`, false);
            // Reload table to update both main and blocked tables
            setTimeout(loadMacs, 1000);
        } else {
            showResult('macs', `❌ Error: ${result.message}`, true);
        }
    } catch (e) {
        showResult('macs', '❌ Error de red al aislar MAC', true);
    }
}

async function unisolateMac(ip, mac) {
    if (!confirm(`¿Desbloquear MAC ${mac} en el switch ${ip}?`)) return;
    showResult('macs', `⏳ Desaislando ${mac}...`, false);
    try {
        const response = await fetch('/admin/expect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'unisolate', params: { ip, mac } }),
            credentials: 'include'
        });
        const result = await response.json();
        if (result.success) {
            showResult('macs', `✅ MAC ${mac} desbloqueada correctamente`, false);
            // Reload table to update button state
            setTimeout(loadMacs, 1000);
        } else {
            showResult('macs', `❌ Error: ${result.message}`, true);
        }
    } catch (e) {
        showResult('macs', '❌ Error de red al desaislar MAC', true);
    }
}

// --- MAC TABLE ---
async function loadSwitchesForMacs() {
    const macSwitchSelect = document.getElementById('mac-switch');
    if (!macSwitchSelect) return;
    try {
        const response = await fetch('/admin/expect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'list_switches' }),
            credentials: 'include'
        });
        const result = await response.json();
        const data = parseSwitchesMessage(result.message);
        const switches = data.switches || [];
        macSwitchSelect.innerHTML = '<option value="" disabled selected>Seleccione un switch</option>';
        switches.forEach(sw => {
            const option = document.createElement('option');
            option.value = sw.ip;
            option.textContent = sw.name ? `${sw.name} (${sw.ip})` : sw.ip;
            macSwitchSelect.appendChild(option);
        });
    } catch (e) { console.error(e); }
}

// --- ORCHESTRATION EXECUTION ---
function serializeConfig() {
    const actions = [];
    const globalBlock = { context: 'global', parameters: {} };
    document.querySelectorAll('#global-config-container .param-wrapper .config-row').forEach(row => {
        const key = row.querySelector('.param-label').dataset.key;
        const input = row.querySelector('input, select');
        if (key && input) globalBlock.parameters[key] = input.value;
    });
    if (Object.keys(globalBlock.parameters).length > 0) actions.push(globalBlock);

    document.querySelectorAll('#interface-config-container .config-block').forEach(block => {
        const portInput = block.querySelector('.port-input');
        if (!portInput) return;
        const ifaceBlock = { context: 'interface', ports: portInput.value, parameters: {} };
        block.querySelectorAll('.interface-params-list .param-wrapper .config-row').forEach(row => {
            const key = row.querySelector('.param-label').dataset.key;
            const input = row.querySelector('input, select');
            if (key && input) ifaceBlock.parameters[key] = input.value;
        });
        actions.push(ifaceBlock);
    });
    return actions;
}

async function handleOrchestration(e) {
    e.preventDefault();
    const ip = document.getElementById('target-ip').value;
    const auth_required = document.getElementById('auth_required').checked;
    const dry_run = document.getElementById('dry_run').checked;
    const actions = serializeConfig();

    if (!ip) { alert("Seleccione un switch"); return; }
    if (actions.length === 0) { alert("Añada al menos una configuración"); return; }

    const output = document.getElementById('output');
    output.textContent = "⏳ Ejecutando orquestación...";
    output.className = "output";
    output.style.display = "block";

    try {
        const response = await fetch('/admin/expect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                action: 'run',
                params: { ip, auth_required, dry_run, actions }
            }),
            credentials: 'include'
        });
        const result = await response.json();
        output.textContent = result.message || (result.success ? "Éxito" : "Error");
        output.style.borderColor = result.success ? "rgba(16, 185, 129, 0.2)" : "rgba(239, 68, 68, 0.2)";
        output.style.color = result.success ? "var(--text-primary)" : "#fca5a5";
    } catch (e) {
        output.textContent = "Error de red";
        output.className = "output error";
    }
}

async function loadMacs() {
    const ip = document.getElementById('mac-switch').value;
    if (!ip) { alert("Seleccione un switch"); return; }

    const tbody = document.querySelector("#mac-table tbody");
    const output = document.getElementById('mac-output');
    tbody.innerHTML = '<tr><td colspan="4" class="loading">Consultando tabla MAC...</td></tr>';
    output.classList.add('hidden');

    try {
        // 1. Fetch current isolation state
        let isolatedMacs = {};
        try {
            const stateResp = await fetch('/admin/expect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'get_state', params: { ip } }),
                credentials: 'include'
            });
            const stateResult = await stateResp.json();
            if (stateResult.success) {
                const stateData = typeof stateResult.message === 'string' ? JSON.parse(stateResult.message) : stateResult.message;
                isolatedMacs = stateData.mac_acl || {};
            }
        } catch (e) { console.warn("No se pudo obtener el estado de aislamiento:", e); }

        // 2. Fetch MAC table
        const response = await fetch('/admin/expect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'mac_table', params: { ip } }),
            credentials: 'include'
        });
        const result = await response.json();
        const outputElement = document.getElementById('result-macs');

        if (result.success) {
            const macs = parseMacTable(result.message);
            tbody.innerHTML = "";

            if (macs.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4">No se detectaron MACs en la respuesta del switch</td></tr>';
                outputElement.textContent = "Consulta realizada, pero no se encontraron MACs dinámicas.";
                outputElement.className = "result success";
            } else {
                macs.forEach(item => {
                    // Normalizar MAC para comparar con el estado (indexado por : )
                    const macKey = item.mac.toLowerCase().replace(/[^0-9a-f]/g, '').match(/.{1,2}/g).join(':');
                    const isIsolated = !!isolatedMacs[macKey];

                    const tr = document.createElement("tr");
                    tr.innerHTML = `
                        <td><code>${escapeHtml(item.mac)}</code></td>
                        <td><span class="badge">${escapeHtml(item.vlan)}</span></td>
                        <td>${escapeHtml(item.port)}</td>
                        <td>
                            ${isIsolated
                            ? `<button class="btn btn-blue btn-small" onclick="unisolateMac('${ip}', '${item.mac}')">Desaislar</button>`
                            : `<button class="btn btn-red btn-small" onclick="isolateMac('${ip}', '${item.mac}')">Aislar</button>`
                        }
                        </td>
                    `;
                    tbody.appendChild(tr);
                });
                outputElement.textContent = `Se encontraron ${macs.length} entrada(s).`;
                outputElement.className = "result success";
            }

            // --- POPULATE BLOCKED MACS TABLE ---
            const blockedTbody = document.querySelector("#blocked-macs-table tbody");
            blockedTbody.innerHTML = "";
            const blockedKeys = Object.keys(isolatedMacs);
            if (blockedKeys.length === 0) {
                blockedTbody.innerHTML = '<tr><td colspan="4">No hay MACs bloqueadas en este switch.</td></tr>';
            } else {
                blockedKeys.forEach(mac => {
                    const info = isolatedMacs[mac];
                    const tr = document.createElement("tr");
                    tr.innerHTML = `
                        <td><code>${escapeHtml(mac)}</code></td>
                        <td><span class="badge">${escapeHtml(info.acl_name || info.rule_id || '-')}</span></td>
                        <td>${new Date(info.blocked_at).toLocaleString()}</td>
                        <td>
                            <button class="btn btn-blue btn-small" onclick="unisolateMac('${ip}', '${mac}')">Desaislar</button>
                        </td>
                    `;
                    blockedTbody.appendChild(tr);
                });
            }
        } else {
            tbody.innerHTML = "";
            outputElement.textContent = "Error: " + (result.message || "Error desconocido en el servidor");
            outputElement.className = "result error";
        }
    } catch (e) {
        tbody.innerHTML = "";
        const outputElement = document.getElementById('result-macs');
        outputElement.textContent = "Error de red";
        outputElement.className = "result error";
    }
}

// --- INITIALIZATION ---
window.addEventListener('DOMContentLoaded', () => {
    const saved = sessionStorage.getItem("expectSelectedSection") || 'config';
    const btn = document.getElementById('btn' + saved.charAt(0).toUpperCase() + saved.slice(1));
    switchSection(saved, btn);

    document.getElementById('target-ip')?.addEventListener('change', (e) => {
        sessionStorage.setItem('expectSelectedIp', e.target.value);
        updateAuthFeedback(e.target.value);
        loadProfileParams();
    });
    document.getElementById('auth_required')?.addEventListener('change', toggleAuthWarning);
    document.getElementById('switch-form')?.addEventListener('submit', saveSwitch);
    document.getElementById('expect-form')?.addEventListener('submit', handleOrchestration);
    document.getElementById('btn-load-macs')?.addEventListener('click', loadMacs);

    // Close menus on click outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.add-param-container')) {
            document.querySelectorAll('.param-menu').forEach(m => m.style.display = 'none');
        }
    });

    // Handle "No password" checkbox
    document.getElementById('sw-no-pass')?.addEventListener('change', (e) => {
        const passInput = document.getElementById('sw-pass');
        if (e.target.checked) {
            passInput.value = '';
            passInput.disabled = true;
        } else {
            passInput.disabled = false;
        }
    });
});

async function handleSoftReset() {
    const ip = document.getElementById('target-ip').value;
    if (!ip || !confirm("¿Restablecer interfaces a fábrica?")) return;
    showResult('config', '⏳ Reseteando...', false);
    // Fetch logic...
}
