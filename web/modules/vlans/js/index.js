/* /web/00-js/vlans/index.js */

// --- GLOBAL STATE ---
let lastStatus = '';
let pollInterval = 2000;
let unchangedCount = 0;
let statusTimerId = null;
let vlanCache = {};

// --- UTILS ---
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function isValidCIDR(ip) {
    const parts = ip.split('/');
    if (parts.length !== 2) return false;
    const ipAddr = parts[0];
    const mask = parseInt(parts[1]);
    if (isNaN(mask) || mask < 1 || mask > 32) return false;
    const ipParts = ipAddr.split('.');
    if (ipParts.length !== 4) return false;
    for (let part of ipParts) {
        const num = parseInt(part);
        if (isNaN(num) || num < 0 || num > 255) return false;
    }
    return true;
}

function getNetworkInfo(ipCidr) {
    try {
        const [ip, maskStr] = ipCidr.split('/');
        const mask = parseInt(maskStr);
        const ipParts = ip.split('.').map(Number);
        const ipNum = (ipParts[0] << 24) | (ipParts[1] << 16) | (ipParts[2] << 8) | ipParts[3];
        const maskNum = (0xFFFFFFFF << (32 - mask)) >>> 0;
        const networkNum = (ipNum & maskNum) >>> 0;
        const broadcastNum = (networkNum | (~maskNum & 0xFFFFFFFF)) >>> 0;
        return { ipNum: ipNum >>> 0, networkNum, broadcastNum };
    } catch (e) { return null; }
}

function isValidNetworkIP(ip) {
    if (!isValidCIDR(ip)) return false;
    const info = getNetworkInfo(ip);
    return info && info.ipNum === info.networkNum;
}

function isValidInterfaceIP(ip) {
    if (!isValidCIDR(ip)) return false;
    const info = getNetworkInfo(ip);
    return info && info.ipNum !== info.networkNum && info.ipNum !== info.broadcastNum;
}

function isIpInNetwork(ipInterface, ipNetwork) {
    try {
        const ipParts = ipInterface.split('/')[0].split('.').map(p => parseInt(p));
        const netParts = ipNetwork.split('/')[0].split('.').map(p => parseInt(p));
        const mask = parseInt(ipNetwork.split('/')[1]);
        const ipNum = (ipParts[0] << 24) | (ipParts[1] << 16) | (ipParts[2] << 8) | ipParts[3];
        const netNum = (netParts[0] << 24) | (netParts[1] << 16) | (netParts[2] << 8) | netParts[3];
        const maskNum = (0xFFFFFFFF << (32 - mask)) >>> 0;
        return (ipNum & maskNum) === (netNum & maskNum);
    } catch (e) { return false; }
}

function validateVlanFields(name, ipInterface, ipNetwork) {
    if (!name) return "Nombre no puede estar vacío";
    if (!ipInterface) return "IP de interfaz no puede estar vacía";
    if (!isValidCIDR(ipInterface)) return "Formato de IP de interfaz inválido (usar CIDR)";
    if (!isValidInterfaceIP(ipInterface)) return "IP de interfaz no puede ser dirección de red o broadcast";
    if (!ipNetwork) return "IP de red no puede estar vacía";
    if (!isValidNetworkIP(ipNetwork)) return "IP de red debe terminar en 0 (ej: .0/24)";
    if (!isIpInNetwork(ipInterface, ipNetwork)) return "La IP de interfaz no pertenece a la red indicada";
    return null;
}

// --- NAVIGATION ---
function switchSection(sectionId, btn) {
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    const target = document.getElementById('section-' + sectionId);
    if (target) target.classList.add('active');

    document.querySelectorAll('.sidebar button').forEach(b => b.classList.remove('selected'));
    if (btn) btn.classList.add('selected');

    sessionStorage.setItem("vlansSelectedSection", sectionId);
    if (btn) sessionStorage.setItem("vlansSelectedBtnId", btn.id);

    if (sectionId === 'config') loadVlans();
    if (sectionId === 'status') refreshStatus();
}

// --- CORE ACTIONS ---
async function runVlansAction(action, btn) {
    switchSection('status', btn);
    const container = document.getElementById('status-container');
    container.innerHTML = `<div class="loading">⏳ Ejecutando acción: ${action.toUpperCase()}...</div>`;

    try {
        const resp = await fetch('/admin/vlans', {
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
    container.innerHTML = '<div class="loading">Cargando estado de VLANs...</div>';

    try {
        const resp = await fetch('/admin/vlans', {
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

function fetchModuleStatus() {
    fetch('/admin/status', { credentials: 'include' })
        .then(resp => resp.json())
        .then(data => {
            const status = data['vlans'] || 'DESCONOCIDO';
            if (status !== lastStatus) {
                lastStatus = status;
                const statusBox = document.getElementById('module-status');
                statusBox.textContent = `Estado: ${status}`;
                statusBox.className = 'status-box ' + status.toLowerCase();
            }
            clearTimeout(statusTimerId);
            statusTimerId = setTimeout(fetchModuleStatus, pollInterval);
        });
}

// --- CONFIGURATION ---
async function loadVlans() {
    try {
        const resp = await fetch("/admin/config/vlans/vlans.json", { credentials: "include" });
        if (!resp.ok) return;
        const data = await resp.json();
        const vlans = data.vlans || [];
        const tbody = document.querySelector("#vlansTable tbody");
        tbody.innerHTML = "";
        vlanCache = {};

        vlans.sort((a, b) => a.id - b.id).forEach(v => {
            vlanCache[v.id] = v;
            const isProtected = (v.id === 1 || v.id === 2);
            const tr = document.createElement("tr");
            tr.dataset.id = v.id;
            tr.innerHTML = `
                <td><span class="vlan-id ${isProtected ? 'protected' : ''}">${v.id}</span></td>
                <td><strong>${escapeHtml(v.name || "")}</strong></td>
                <td><code class="ip-code">${escapeHtml(v.ip_interface || "")}</code></td>
                <td><code class="ip-code">${escapeHtml(v.ip_network || "")}</code></td>
                <td>
                    <button class="btn btn-blue btn-small" onclick="editRow(${v.id})">✏️ Modificar</button>
                    ${!isProtected ? `<button class="btn btn-red btn-small" onclick="deleteVlan(${v.id})">🗑️ Borrar</button>` : '<span class="status-locked">🔒 Protegida</span>'}
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error("Error loading VLANs:", err);
    }
}

function editRow(id) {
    const tr = document.querySelector(`tr[data-id="${id}"]`);
    const v = vlanCache[id];
    tr.innerHTML = `
        <td>${v.id}</td>
        <td><input type="text" value="${v.name || ""}"></td>
        <td><input type="text" value="${v.ip_interface || ""}"></td>
        <td><input type="text" value="${v.ip_network || ""}"></td>
        <td>
            <button class="btn-edit" onclick="saveRow(${id})">💾</button>
            <button class="btn-delete" onclick="loadVlans()">❌</button>
        </td>
    `;
}

async function saveRow(id) {
    const tr = document.querySelector(`tr[data-id="${id}"]`);
    const inputs = tr.querySelectorAll("input");
    const [name, ip_interface, ip_network] = Array.from(inputs).map(i => i.value.trim());

    const err = validateVlanFields(name, ip_interface, ip_network);
    if (err) { alert(err); return; }

    try {
        const resp = await fetch("/admin/vlans", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ action: "config", params: { action: "add", id, name, ip_interface, ip_network } })
        });
        if ((await resp.json()).success) { loadVlans(); }
    } catch (e) { }
}

async function deleteVlan(id) {
    if (!confirm(`¿Eliminar VLAN ${id}?`)) return;
    try {
        const resp = await fetch("/admin/vlans", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ action: "config", params: { action: "remove", id } })
        });
        if ((await resp.json()).success) loadVlans();
    } catch (e) { }
}

// --- INIT ---
window.addEventListener('DOMContentLoaded', () => {
    const savedSection = sessionStorage.getItem("vlansSelectedSection") || 'info';
    const savedBtnId = sessionStorage.getItem("vlansSelectedBtnId");
    const btn = document.getElementById(savedBtnId) || document.getElementById('btn' + savedSection.charAt(0).toUpperCase() + savedSection.slice(1));

    switchSection(savedSection, btn);
    fetchModuleStatus();

    document.getElementById('vlan-form')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const id = parseInt(document.getElementById('vlan-id').value);
        const name = document.getElementById('vlan-name').value;
        const ip_interface = document.getElementById('vlan-ip-interface').value;
        const ip_network = document.getElementById('vlan-ip-network').value;

        const err = validateVlanFields(name, ip_interface, ip_network);
        if (err) { alert(err); return; }

        try {
            const resp = await fetch("/admin/vlans", {
                method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include",
                body: JSON.stringify({ action: "config", params: { action: "add", id, name, ip_interface, ip_network } })
            });
            const data = await resp.json();
            if (data.success) { e.target.reset(); loadVlans(); }
            else alert(data.message);
        } catch (e) { }
    });
});
