/* /web/00-js/nat/index.js */

// --- GLOBAL STATE ---
let lastStatus = '';
let pollInterval = 2000;
let unchangedCount = 0;
let statusTimerId = null;
let userEditing = false;
let dependencyTimerId = null;

// --- UTILS ---
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// --- NAVIGATION ---
function switchSection(sectionId, btn) {
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    const target = document.getElementById('section-' + sectionId);
    if (target) target.classList.add('active');

    document.querySelectorAll('.sidebar button').forEach(b => b.classList.remove('selected'));
    if (btn) btn.classList.add('selected');

    sessionStorage.setItem("natSelectedSection", sectionId);
    if (btn) sessionStorage.setItem("natSelectedBtnId", btn.id);

    if (sectionId === 'config') {
        loadWanInterface();
        loadNatInterface();
    }
    if (sectionId === 'status') refreshStatus();
}

// --- CORE ACTIONS (from menu.js) ---
async function runNatAction(action, btn) {
    switchSection('status', btn);
    document.getElementById('status-container').innerHTML = `<div class="loading">⏳ Ejecutando acción: ${action.toUpperCase()}...</div>`;

    try {
        const response = await fetch('/admin/nat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action }),
            credentials: 'include'
        });
        const data = await response.json();

        const container = document.getElementById('status-container');
        if (data.success) {
            container.innerHTML = `
                <div style="color: #10b981; font-weight: 600; margin-bottom: 10px;">✅ Acción completada con éxito</div>
                <div class="status-content">${escapeHtml(data.message)}</div>
            `;
        } else {
            container.innerHTML = `
                <div style="color: #ef4444; font-weight: 600; margin-bottom: 10px;">❌ Error</div>
                <div class="status-content">${escapeHtml(data.message || 'Error desconocido')}</div>
            `;
        }
    } catch (error) {
        document.getElementById('status-container').innerHTML = `<div style="color: #ef4444;">❌ Error de conexión al servidor</div>`;
    }
}

// --- STATUS MODULE (from status.js) ---
async function refreshStatus() {
    const container = document.getElementById('status-container');
    const btn = document.getElementById('btnRefresh');
    if (btn) btn.disabled = true;

    container.innerHTML = '<div class="loading">Cargando estado de NAT...</div>';

    try {
        const response = await fetch('/admin/nat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'status' }),
            credentials: 'include'
        });

        const data = await response.json();
        if (data.success) {
            container.innerHTML = `
                <div style="color: #10b981; font-weight: 600; margin-bottom: 10px;">✅ Estado obtenido correctamente</div>
                <div class="status-content">${escapeHtml(data.message)}</div>
            `;
        } else {
            container.innerHTML = `<div style="color: #ef4444;">❌ Error: ${escapeHtml(data.message || 'Error desconocido')}</div>`;
        }
    } catch (error) {
        container.innerHTML = `<div style="color: #ef4444;">❌ Error al obtener el estado</div>`;
    } finally {
        if (btn) btn.disabled = false;
    }
}

// Dependency checking (WAN must be active for NAT)
async function checkDependencies() {
    const btnStart = document.getElementById('btnStart');
    const depWan = document.getElementById('dep-wan');
    if (!depWan) return;

    try {
        const wanResp = await fetch('/admin/wan/info', { credentials: 'include' });
        const wanData = await wanResp.json();
        if (wanData.status === 1) {
            depWan.innerHTML = '✅ WAN: Activo';
            depWan.style.color = '#059669';
            if (btnStart) {
                btnStart.disabled = false;
                btnStart.title = '';
            }
        } else {
            depWan.innerHTML = '❌ WAN: Inactivo (Requerido)';
            depWan.style.color = '#dc2626';
            if (btnStart) {
                btnStart.disabled = true;
                btnStart.title = 'WAN debe estar activo primero';
            }
        }
    } catch {
        depWan.innerHTML = '⚠️ WAN: Error al verificar';
        if (btnStart) btnStart.disabled = true;
    }

    clearTimeout(dependencyTimerId);
    dependencyTimerId = setTimeout(checkDependencies, 5000);
}

// Module status polling
function fetchModuleStatus() {
    fetch('/admin/status', { credentials: 'include' })
        .then(response => response.json())
        .then(data => {
            const status = data['nat'] || 'DESCONOCIDO';
            if (status !== lastStatus) {
                lastStatus = status;
                const statusBox = document.getElementById('module-status');
                statusBox.textContent = `Estado: ${status}`;
                statusBox.className = 'status-box ' + status.toLowerCase();
            }
            clearTimeout(statusTimerId);
            statusTimerId = setTimeout(fetchModuleStatus, 5000);
        })
        .catch(() => {
            statusTimerId = setTimeout(fetchModuleStatus, 10000);
        });
}

// --- CONFIG MODULE ---
async function loadWanInterface() {
    try {
        const response = await fetch("/admin/config/wan/wan.json", { credentials: "include" });
        if (response.ok) {
            const wanConfig = await response.json();
            document.getElementById("wan-details").textContent = `${wanConfig.interface || "No configurada"} (Modo: ${wanConfig.mode || "N/A"})`;
            document.getElementById("wan-info-container").style.display = "block";
        }
    } catch (e) { }
}

async function loadNatInterface() {
    try {
        const response = await fetch("/admin/config/nat/nat.json", { credentials: "include" });
        if (response.ok) {
            const natConfig = await response.json();
            const natInterface = natConfig.interface || "No configurada";
            document.getElementById("nat-details").textContent = `${natInterface} (Estado: ${natConfig.status === 1 ? 'Activo' : 'Inactivo'})`;
            document.getElementById("nat-info-container").style.display = "block";
            if (!userEditing) document.getElementById("interface").value = (natInterface !== "No configurada") ? natInterface : "";
        }
    } catch (e) { }
}

// --- INIT ---
window.addEventListener('DOMContentLoaded', () => {
    const savedSection = sessionStorage.getItem("natSelectedSection") || 'info';
    const savedBtnId = sessionStorage.getItem("natSelectedBtnId");
    const btn = document.getElementById(savedBtnId) || document.getElementById('btn' + savedSection.charAt(0).toUpperCase() + savedSection.slice(1));

    switchSection(savedSection, btn);
    fetchModuleStatus();
    checkDependencies();

    document.getElementById("interface")?.addEventListener('input', () => { userEditing = true; });
    document.getElementById('nat-form')?.addEventListener('submit', handleFormSubmit);
});

async function handleFormSubmit(e) {
    e.preventDefault();
    const resultDiv = document.getElementById("config-result");
    const iface = document.getElementById("interface").value.trim();

    resultDiv.textContent = "⏳ Guardando...";
    resultDiv.style.color = "#4b5563";

    if (!/^[a-zA-Z0-9._-]+$/.test(iface)) {
        resultDiv.textContent = "❌ Formato de interfaz inválido";
        resultDiv.style.color = "#ef4444";
        return;
    }

    try {
        const response = await fetch("/admin/nat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ action: "config", params: { interface: iface } })
        });
        const data = await response.json();
        if (response.ok) {
            resultDiv.textContent = "✅ " + data.message;
            resultDiv.style.color = "#059669";
            loadNatInterface();
            userEditing = false;
        } else {
            showToast("❌ Error: " + (data.detail || data.message)); resultDiv.textContent = "";
            resultDiv.style.color = "#ef4444";
        }
    } catch (err) {
        resultDiv.textContent = "❌ Error de conexión";
        resultDiv.style.color = "#ef4444";
    }
}
