/* /web/00-js/wan/index.js */

// --- GLOBAL STATE ---
let lastStatus = '';
let pollInterval = 2000;
let unchangedCount = 0;
let statusTimerId = null;
let userEditing = false;

// --- UTILS ---
function isValidIPv4(ip) {
    const regex = /^(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)){3}$/;
    return regex.test(ip);
}

function isValidCIDR(mask) {
    const n = Number(mask);
    return Number.isInteger(n) && n >= 0 && n <= 32;
}

function isValidDNSList(dns) {
    const servers = dns.split(",").map(d => d.trim()).filter(Boolean);
    if (servers.length === 0) return false;
    return servers.every(isValidIPv4);
}

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

    sessionStorage.setItem("wanSelectedSection", sectionId);
    if (btn) sessionStorage.setItem("wanSelectedBtnId", btn.id);

    if (sectionId === 'config') loadWanConfiguration();
    if (sectionId === 'status') refreshStatus();
}

// --- CORE ACTIONS (from menu.js) ---
async function runWanAction(action, btn) {
    // Switch to status section to show results
    switchSection('status', btn);

    document.getElementById('status-container').innerHTML = `<div class="loading">⏳ Ejecutando acción: ${action.toUpperCase()}...</div>`;

    try {
        const response = await fetch('/admin/wan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action }),
            credentials: 'include'
        });
        const data = await response.json();

        const container = document.getElementById('status-container');
        if (data.success) {
            container.innerHTML = `
                <div style="color: #48bb78; font-weight: 600; margin-bottom: 10px;">✅ Acción completada con éxito</div>
                <div class="status-content">${escapeHtml(data.message)}</div>
            `;
        } else {
            container.innerHTML = `
                <div style="color: #f56565; font-weight: 600; margin-bottom: 10px;">❌ Error</div>
                <div class="status-content">${escapeHtml(data.message || 'Error desconocido')}</div>
            `;
        }
    } catch (error) {
        console.error("Error al ejecutar la acción:", error);
        document.getElementById('status-container').innerHTML = `<div style="color: #f56565;">❌ Error de conexión al servidor</div>`;
    }
}

// --- STATUS MODULE (from status.js) ---
async function refreshStatus() {
    const container = document.getElementById('status-container');
    const btn = document.getElementById('btnRefresh');
    if (btn) btn.disabled = true;

    container.innerHTML = '<div class="loading">Cargando estado de WAN...</div>';

    try {
        const response = await fetch('/admin/wan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'status' }),
            credentials: 'include'
        });

        const data = await response.json();
        if (data.success) {
            container.innerHTML = `
                <div style="color: #48bb78; font-weight: 600; margin-bottom: 10px;">✅ Estado obtenido correctamente</div>
                <div class="status-content">${escapeHtml(data.message)}</div>
            `;
        } else {
            container.innerHTML = `<div style="color: #f56565;">❌ Error: ${escapeHtml(data.message || 'Error desconocido')}</div>`;
        }
    } catch (error) {
        container.innerHTML = `<div style="color: #f56565;">❌ Error al obtener el estado</div>`;
    } finally {
        if (btn) btn.disabled = false;
    }
}

// Polling for module status box
function fetchModuleStatus() {
    fetch('/admin/status', { credentials: 'include' })
        .then(response => response.json())
        .then(data => {
            const status = data['wan'] || 'DESCONOCIDO';
            if (status === lastStatus) {
                unchangedCount++;
                if (unchangedCount > 3) pollInterval = 5000;
            } else {
                lastStatus = status;
                unchangedCount = 0;
                pollInterval = 2000;
                const statusBox = document.getElementById('module-status');
                statusBox.textContent = `Estado: ${status}`;
                statusBox.className = 'status-box ' + status.toLowerCase();
            }
            clearTimeout(statusTimerId);
            statusTimerId = setTimeout(fetchModuleStatus, pollInterval);
        })
        .catch(() => {
            statusTimerId = setTimeout(fetchModuleStatus, 5000);
        });
}

// --- CONFIG MODULE (from config.js) ---
async function loadWanConfiguration() {
    try {
        const response = await fetch("/admin/config/wan/wan.json", { credentials: "include" });
        if (response.ok) {
            const wanConfig = await response.json();
            const wanInterface = wanConfig.interface || "No configurada";
            const wanMode = wanConfig.mode || "No definido";
            const wanStatus = wanConfig.status === 1 ? "Activo" : "Inactivo";

            document.getElementById("wan-details").textContent = `${wanInterface} (Modo: ${wanMode}, Estado: ${wanStatus})`;
            document.getElementById("wan-info-container").style.display = "block";
            document.getElementById("dhcp-notice").style.display = (wanMode === "dhcp") ? "block" : "none";

            if (!userEditing) {
                document.getElementById("interface").value = wanConfig.interface || "";
                document.getElementById("mode").value = wanConfig.mode || "dhcp";
                document.getElementById("manual-fields").classList.toggle("hidden", wanConfig.mode !== "manual");
                if (wanConfig.mode === "manual") {
                    document.getElementById("ip").value = wanConfig.ip || "";
                    document.getElementById("mask").value = wanConfig.mask || "";
                    document.getElementById("gateway").value = wanConfig.gateway || "";
                    document.getElementById("dns").value = wanConfig.dns || "";
                }
            }
        }
    } catch (err) { console.info("No wan config found."); }
}

// --- INIT ---
window.addEventListener('DOMContentLoaded', () => {
    const savedSection = sessionStorage.getItem("wanSelectedSection") || 'info';
    const savedBtnId = sessionStorage.getItem("wanSelectedBtnId");
    const btn = document.getElementById(savedBtnId) || document.getElementById('btn' + savedSection.charAt(0).toUpperCase() + savedSection.slice(1));

    switchSection(savedSection, btn);
    fetchModuleStatus();

    // Form setup
    const modeSelect = document.getElementById("mode");
    modeSelect?.addEventListener("change", () => {
        document.getElementById("manual-fields").classList.toggle("hidden", modeSelect.value !== "manual");
        document.getElementById("dhcp-notice").style.display = (modeSelect.value === "dhcp") ? "block" : "none";
        userEditing = true;
    });

    ['interface', 'ip', 'mask', 'gateway', 'dns'].forEach(id => {
        document.getElementById(id)?.addEventListener('input', () => { userEditing = true; });
    });

    document.getElementById('wan-form')?.addEventListener('submit', handleFormSubmit);
});

async function handleFormSubmit(e) {
    e.preventDefault();
    const resultDiv = document.getElementById("config-result");
    resultDiv.textContent = "⏳ Guardando...";
    resultDiv.style.color = "#4a5568";

    const params = {
        interface: document.getElementById("interface").value.trim(),
        mode: document.getElementById("mode").value
    };

    if (params.mode === "manual") {
        params.ip = document.getElementById("ip").value.trim();
        params.mask = document.getElementById("mask").value.trim();
        params.gateway = document.getElementById("gateway").value.trim();
        params.dns = document.getElementById("dns").value.trim();

        if (!isValidIPv4(params.ip) || !isValidIPv4(params.gateway)) {
            resultDiv.textContent = "❌ IP o Gateway inválido";
            resultDiv.style.color = "#f56565";
            return;
        }
    }

    try {
        const response = await fetch("/admin/wan", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ action: "config", params })
        });
        const data = await response.json();
        if (response.ok) {
            resultDiv.textContent = "✅ " + data.message;
            resultDiv.style.color = "#48bb78";
            loadWanConfiguration();
            userEditing = false;
        } else {
            showToast("❌ Error: " + (data.detail || data.message)); resultDiv.textContent = "";
            resultDiv.style.color = "#f56565";
        }
    } catch (err) {
        resultDiv.textContent = "❌ Error de conexión";
        resultDiv.style.color = "#f56565";
    }
}
