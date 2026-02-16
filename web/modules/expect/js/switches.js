/* /web/modules/expect/js/switches.js */

let switchesCache = {};

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
    const result = document.getElementById(`result-${section}`);
    if (!result) return;
    result.textContent = message;
    result.style.display = 'block';
    result.style.color = isError ? 'var(--error)' : 'var(--success)';
}

// --- SWITCHES TABLE ---
async function loadSwitchesForTable() {
    const tbody = document.querySelector("#switches-table tbody");
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="3" class="loading">Cargando switches...</td></tr>';
    try {
        const response = await fetch('/admin/expect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'list_switches' }),
            credentials: 'include'
        });
        const result = await response.json();
        if (!result.success) {
            tbody.innerHTML = `<tr><td colspan="3" style="color:var(--error); text-align:center;">Error: ${escapeHtml(result.message)}</td></tr>`;
            return;
        }
        const data = parseSwitchesMessage(result.message);
        const switches = data.switches || (Array.isArray(data) ? data : []);
        switchesCache = {};
        switches.forEach(sw => { if (sw && sw.ip) switchesCache[sw.ip] = sw; });
        tbody.innerHTML = "";
        if (switches.length === 0) {
            tbody.innerHTML = '<tr><td colspan="3" style="text-align: center; color: var(--text-secondary); padding: 20px;">No hay switches registrados</td></tr>';
            return;
        }
        switches.forEach(sw => {
            const tr = document.createElement("tr");
            tr.dataset.ip = sw.ip;
            renderRow(tr, sw);
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.error(e);
        tbody.innerHTML = '<tr><td colspan="3" style="color:var(--error); text-align:center;">Error de red</td></tr>';
    }
}

function renderRow(tr, sw) {
    tr.innerHTML = `
        <td>
            <div style="font-weight: 600; color: var(--text-primary);">${escapeHtml(sw.name || 'Sin nombre')}</div>
            <div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 4px;">User: ${escapeHtml(sw.user || '-')}</div>
        </td>
        <td>
            <code>${escapeHtml(sw.ip || '')}</code>
            <div style="margin-top: 5px; display: flex; gap: 5px; flex-wrap: wrap;">
                <span class="badge" style="background: rgba(225, 29, 72, 0.1); color: var(--accent-color); font-size: 0.7rem;">${escapeHtml(sw.profile || '')}</span>
                <span class="badge" style="background: rgba(59, 130, 246, 0.1); color: #3b82f6; font-size: 0.7rem;">${escapeHtml(sw.protocol || 'telnet')}</span>
                <span class="badge" style="background: rgba(16, 185, 129, 0.1); color: #10b981; font-size: 0.7rem;">${sw.max_ports || 24} ports</span>
            </div>
        </td>
        <td>
            <div class="action-group">
                <button class="btn btn-blue btn-small" onclick="editRow('${sw.ip}')" title="Editar">✏️</button>
                <button class="btn btn-red btn-small" onclick="deleteSwitch('${sw.ip}')" title="Eliminar">🗑️</button>
            </div>
        </td>
    `;
}

function editRow(ip) {
    const sw = switchesCache[ip];
    if (!sw) return;
    const tr = document.querySelector(`tr[data-ip="${ip}"]`);
    if (!tr) return;

    tr.innerHTML = `
        <td colspan="2">
            <div class="grid-form" style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; background: rgba(255,255,255,0.02); padding: 10px; border-radius: 4px;">
                <div class="table-form-group">
                    <label>Nombre</label>
                    <input type="text" class="inline-input" id="edit-name-${ip}" value="${escapeHtml(sw.name)}">
                </div>
                <div class="table-form-group">
                    <label>IP</label>
                    <input type="text" class="inline-input" id="edit-ip-${ip}" value="${escapeHtml(sw.ip)}">
                </div>
                <div class="table-form-group">
                    <label>Usuario</label>
                    <input type="text" class="inline-input" id="edit-user-${ip}" value="${escapeHtml(sw.user)}">
                </div>
                <div class="table-form-group">
                    <label>Perfil</label>
                    <select id="edit-profile-${ip}" class="inline-input" style="height: 35px;">
                        <option value="cisco_ios" ${sw.profile === 'cisco_ios' ? 'selected' : ''}>Cisco IOS</option>
                        <option value="tp_link" ${sw.profile === 'tp_link' ? 'selected' : ''}>TP-Link</option>
                    </select>
                </div>
                <div class="table-form-group">
                    <label>Protocolo</label>
                    <select id="edit-protocol-${ip}" class="inline-input" style="height: 35px;">
                        <option value="telnet" ${sw.protocol === 'telnet' ? 'selected' : ''}>Telnet</option>
                        <option value="ssh" ${sw.protocol === 'ssh' ? 'selected' : ''}>SSH</option>
                    </select>
                </div>
                <div class="table-form-group">
                    <label>Puertos</label>
                    <input type="number" class="inline-input" id="edit-ports-${ip}" value="${sw.max_ports}">
                </div>
                <div style="grid-column: 1 / -1; font-size: 0.7rem; color: var(--text-secondary); font-style: italic; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 5px;">
                    🛡️ Las credenciales se mantienen seguras y no son editables desde aquí.
                </div>
            </div>
        </td>
        <td>
            <div class="action-group" style="height: 100%; align-items: flex-end;">
                <button class="btn btn-green btn-small" onclick="saveInline('${ip}')" title="Guardar">💾</button>
                <button class="btn btn-red btn-small" onclick="cancelEdit('${ip}')" title="Cancelar">❌</button>
            </div>
        </td>
    `;
}

function cancelEdit(ip) {
    const tr = document.querySelector(`tr[data-ip="${ip}"]`);
    const sw = switchesCache[ip];
    if (tr && sw) renderRow(tr, sw);
}

async function saveInline(originalIp) {
    const name = document.getElementById(`edit-name-${originalIp}`).value;
    const ip = document.getElementById(`edit-ip-${originalIp}`).value;
    const user = document.getElementById(`edit-user-${originalIp}`).value;
    const profile = document.getElementById(`edit-profile-${originalIp}`).value;
    const protocol = document.getElementById(`edit-protocol-${originalIp}`).value;
    const max_ports = parseInt(document.getElementById(`edit-ports-${originalIp}`).value) || 24;

    const params = { original_ip: originalIp, name, ip, user, profile, protocol, max_ports };

    showResult('switches', '⏳ Actualizando...', false);
    try {
        const response = await fetch('/admin/expect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'update_switch', params }),
            credentials: 'include'
        });
        const result = await response.json();
        if (result.success) {
            showResult('switches', '✅ Cambios guardados', false);
            loadSwitchesForTable();
        } else {
            showResult('switches', '❌ Error: ' + result.message, true);
        }
    } catch (e) {
        showResult('switches', '❌ Error de red', true);
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

    const params = { name, ip, user, profile, protocol, max_ports };
    if (noPass) params.password = "";
    else if (pass) params.password = pass;

    showResult('switches', '⏳ Registrando...', false);
    try {
        const response = await fetch('/admin/expect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'add_switch', params }),
            credentials: 'include'
        });
        const result = await response.json();
        if (result.success) {
            showResult('switches', '✅ Switch registrado satisfactoriamente', false);
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
            showResult('switches', '✅ Switch eliminado correctamente', false);
            loadSwitchesForTable();
        } else {
            showResult('switches', '❌ Error: ' + result.message, true);
        }
    } catch (e) {
        showResult('switches', '❌ Error de red', true);
    }
}

// --- INITIALIZATION ---
window.addEventListener('DOMContentLoaded', () => {
    loadSwitchesForTable();
    document.getElementById('switch-form')?.addEventListener('submit', saveSwitch);

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
