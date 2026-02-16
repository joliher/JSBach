/* /web/00-js/tagging/index.js */

// --- GLOBAL STATE ---
let taggingCache = {};
let vlanCache = {};
let ebtablesCache = {};
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

function showMessage(message) {
    const notification = document.getElementById("notification");
    notification.innerHTML = message.replace(/\n/g, "<br>");
    let type = "info";
    if (message.startsWith("✅")) type = "success";
    else if (message.startsWith("❌")) type = "error";
    else if (message.startsWith("⚠️")) type = "warning";

    notification.className = `show ${type}`;
    setTimeout(() => notification.classList.remove("show"), 6000);
}

function isValidInterfaceName(name) {
    if (!/^[a-zA-Z0-9._-]+$/.test(name)) return false;
    if (name.length > 15) return false;
    if (name === 'br0' || name.startsWith('br0.')) return false;
    return true;
}

function isValidVLANId(id) {
    const num = parseInt(id);
    return !isNaN(num) && num >= 1 && num <= 4094;
}

function validateVLANList(vlanList) {
    if (!vlanList) return { valid: true, errors: [] };
    if (/ /.test(vlanList)) return { valid: false, errors: ['No se permiten espacios'] };
    const parts = vlanList.split(',');
    const errors = [];
    parts.forEach(part => {
        if (!part) errors.push('No se permiten comas consecutivas');
        else if (part.includes('-')) {
            const range = part.split('-');
            if (range.length !== 2) errors.push(`Rango inválido: "${part}"`);
            else {
                const s = parseInt(range[0]), e = parseInt(range[1]);
                if (isNaN(s) || isNaN(e) || s < 1 || s > 4094 || e < 1 || e > 4094) errors.push(`Rango inválido: "${part}"`);
            }
        } else if (!isValidVLANId(part)) errors.push(`${part} no es un ID válido`);
    });
    return { valid: errors.length === 0, errors };
}

function isInterfaceUsedByEbtables(name) {
    for (let vlanId in ebtablesCache) {
        const v = ebtablesCache[vlanId];
        if (v && v.interfaces && v.interfaces.includes(name)) return { used: true, vlanId };
    }
    return { used: false };
}

// --- NAVIGATION ---
function switchSection(sectionId, btn) {
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    const target = document.getElementById('section-' + sectionId);
    if (target) target.classList.add('active');

    document.querySelectorAll('.sidebar button').forEach(b => b.classList.remove('selected'));
    if (btn) btn.classList.add('selected');

    sessionStorage.setItem("taggingSelectedSection", sectionId);
    if (btn) sessionStorage.setItem("taggingSelectedBtnId", btn.id);

    if (sectionId === 'config') loadAllData();
    if (sectionId === 'status') refreshStatus();
}

// --- CORE ACTIONS ---
async function runTaggingAction(action, btn) {
    switchSection('status', btn);
    const container = document.getElementById('status-container');
    container.innerHTML = `<div class="loading">⏳ Ejecutando acción: ${action.toUpperCase()}...</div>`;

    try {
        const resp = await fetch('/admin/tagging', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action }),
            credentials: 'include'
        });
        const data = await resp.json();

        if (data.success) {
            container.innerHTML = `
                <div style="color: #f59e0b; font-weight: 600; margin-bottom: 10px;">✅ Acción completada con éxito</div>
                <div style="border-top: 1px solid rgba(245, 158, 11, 0.2); padding-top: 10px; margin-top: 5px;">${escapeHtml(data.message)}</div>
            `;
        } else {
            container.innerHTML = `
                <div style="color: #ef4444; font-weight: 600; margin-bottom: 10px;">❌ Error</div>
                <div style="border-top: 1px solid rgba(239, 68, 68, 0.2); padding-top: 10px; margin-top: 5px; color: #fca5a5;">${escapeHtml(data.message || 'Error desconocido')}</div>
            `;
        }
    } catch (error) {
        container.innerHTML = `<div style="color: #ef4444;">❌ Error de conexión al servidor</div>`;
    }
}

async function refreshStatus() {
    const container = document.getElementById('status-container');
    container.innerHTML = '<div class="loading">Cargando estado de Tagging...</div>';
    try {
        const resp = await fetch('/admin/tagging', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'status' }),
            credentials: 'include'
        });
        const data = await resp.json();
        if (data.success) {
            container.innerHTML = `
                <div style="color: #f59e0b; font-weight: 600; margin-bottom: 10px;">✅ Estado obtenido correctamente</div>
                <div style="border-top: 1px solid rgba(245, 158, 11, 0.2); padding-top: 10px; margin-top: 5px;">${escapeHtml(data.message)}</div>
            `;
        } else {
            container.innerHTML = `<div style="color: #ef4444;">❌ Error: ${escapeHtml(data.message || 'Error desconocido')}</div>`;
        }
    } catch (e) { container.innerHTML = `<div style="color: #ef4444;">❌ Error al obtener el estado</div>`; }
}

async function checkDependencies() {
    const btnStart = document.getElementById('btnStart');
    try {
        const statusResp = await fetch('/admin/status', { credentials: 'include' });
        const data = await statusResp.json();
        const vlansStatus = data['vlans'] || 'DESCONOCIDO';
        const vlansDiv = document.getElementById('dep-vlans');
        vlansDiv.innerHTML = (vlansStatus === 'ACTIVO' ? '✅' : '❌') + ' VLANs: ' + vlansStatus;
        vlansDiv.style.color = (vlansStatus === 'ACTIVO' ? '#059669' : '#dc2626');
        if (btnStart) btnStart.disabled = (vlansStatus !== 'ACTIVO');
    } catch (e) { }
    clearTimeout(dependencyTimerId);
    dependencyTimerId = setTimeout(checkDependencies, 5000);
}

function fetchModuleStatus() {
    fetch('/admin/status', { credentials: 'include' })
        .then(resp => resp.json())
        .then(data => {
            const status = data['tagging'] || 'DESCONOCIDO';
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

// --- CONFIGURATION ---
async function loadAllData() {
    try {
        const [tagResp, vlanResp, ebtResp] = await Promise.all([
            fetch("/admin/config/tagging/tagging.json", { credentials: "include" }),
            fetch("/admin/config/vlans/vlans.json", { credentials: "include" }),
            fetch("/admin/config/ebtables/ebtables.json", { credentials: "include" })
        ]);

        if (tagResp.ok) {
            const data = await tagResp.json();
            taggingCache = {};
            const list = data.interfaces || [];
            if (Array.isArray(list)) list.forEach(i => taggingCache[i.name] = i);
        }
        if (vlanResp.ok) {
            const data = await vlanResp.json();
            vlanCache = {};
            const list = data.vlans || [];
            if (Array.isArray(list)) list.forEach(i => vlanCache[i.id] = i);
        }
        if (ebtResp.ok) {
            const data = await ebtResp.json();
            ebtablesCache = data.bridged_vlans || data;
        }

        renderTaggingTable();
    } catch (e) {
        console.error("Error loading Tagging data:", e);
    }
}

function renderTaggingTable() {
    const tbody = document.querySelector("#taggingTable tbody");
    tbody.innerHTML = "";
    const names = Object.keys(taggingCache).sort();

    if (names.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" style="text-align: center; color: #94a3b8; padding: 30px;">No hay interfaces configuradas</td></tr>';
        return;
    }

    names.forEach(name => {
        const iface = taggingCache[name];
        const ebt = isInterfaceUsedByEbtables(name);
        const tr = document.createElement("tr");
        tr.dataset.name = name;

        const configHtml = iface.vlan_untag ?
            `<span class="vlan-badge badge-untag">UNTAG: ${iface.vlan_untag}</span>` :
            `<span class="vlan-badge badge-tag">TAG: ${iface.vlan_tag}</span>`;

        tr.innerHTML = `
            <td>
                <div class="state-indicator ${ebt.used ? 'state-warn' : 'state-ok'}">
                    <span>${ebt.used ? '⚠️' : '✅'}</span>
                    <strong>${escapeHtml(name)}</strong>
                    ${ebt.used ? `<small>(VLAN ${ebt.vlanId})</small>` : ''}
                </div>
            </td>
            <td>${configHtml}</td>
            <td>
                <div style="display: flex; gap: 8px;">
                    <button class="btn btn-blue btn-small" onclick="editRow('${name}')">✏️ Modificar</button>
                    <button class="btn btn-red btn-small" onclick="deleteIface('${name}')">🗑️ Eliminar</button>
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function editRow(name) {
    const tr = document.querySelector(`tr[data-name="${name}"]`);
    const i = taggingCache[name];
    tr.innerHTML = `
        <td>${name}</td>
        <td>
            U: <input type="text" id="edit-untag-${name}" value="${i.vlan_untag || ''}" style="width:50px"> 
            T: <input type="text" id="edit-tag-${name}" value="${i.vlan_tag || ''}" style="width:100px">
        </td>
        <td>
            <button class="btn-edit" onclick="saveRow('${name}')">💾</button>
            <button class="btn-delete" onclick="loadAllData()">❌</button>
        </td>
    `;
}

async function saveRow(name) {
    const untag = document.getElementById(`edit-untag-${name}`).value.trim();
    const tag = document.getElementById(`edit-tag-${name}`).value.trim();

    if (untag && tag) { showMessage("❌ No se puede configurar UNTAG y TAG simultáneamente"); return; }
    if (tag && !validateVLANList(tag).valid) { showMessage("❌ Lista de VLANs TAG inválida"); return; }

    try {
        const resp = await fetch("/admin/tagging", {
            method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include",
            body: JSON.stringify({ action: "config", params: { action: "add", name, vlan_untag: untag, vlan_tag: tag } })
        });
        if ((await resp.json()).success) { showMessage("✅ Guardado"); loadAllData(); }
    } catch (e) { }
}

async function deleteIface(name) {
    if (!confirm(`¿Eliminar interfaz ${name}?`)) return;
    try {
        const resp = await fetch("/admin/tagging", {
            method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include",
            body: JSON.stringify({ action: "config", params: { action: "remove", name } })
        });
        if ((await resp.json()).success) loadAllData();
    } catch (e) { }
}

// --- INIT ---
window.addEventListener('DOMContentLoaded', () => {
    const savedSection = sessionStorage.getItem("taggingSelectedSection") || 'info';
    const savedBtnId = sessionStorage.getItem("taggingSelectedBtnId");
    const btn = document.getElementById(savedBtnId) || document.getElementById('btn' + savedSection.charAt(0).toUpperCase() + savedSection.slice(1));

    switchSection(savedSection, btn);
    fetchModuleStatus();
    checkDependencies();

    document.getElementById('tagging-form')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = document.getElementById('iface-name').value;
        const vlan_untag = document.getElementById('iface-untag').value;
        const vlan_tag = document.getElementById('iface-tag').value;

        if (vlan_untag && vlan_tag) { showMessage("❌ Elija UNTAG o TAG, no ambos"); return; }

        try {
            const resp = await fetch("/admin/tagging", {
                method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include",
                body: JSON.stringify({ action: "config", params: { action: "add", name, vlan_untag, vlan_tag } })
            });
            const data = await resp.json();
            if (data.success) { e.target.reset(); loadAllData(); showMessage("✅ Agregado"); }
            else showMessage("❌ " + data.message);
        } catch (e) { }
    });
});
