/* /web/js/index.js */

// --- NAVIGATION ---
function switchSection(sectionId) {
    // Legacy support if needed, but now we only have one main dashboard section
    console.log("Switching to", sectionId);
}

// --- STATUS POLLING ---
let lastWanStatus = null;
let lastWanConfig = null;

async function refreshStatus() {
    try {
        const response = await fetch('/admin/status', { credentials: 'include' });
        if (!response.ok) throw new Error("Error en la petición");

        const data = await response.json();

        // Update each card status
        const modules = ["wan", "nat", "firewall", "vlans", "tagging", "dmz", "ebtables", "expect"];
        modules.forEach(mod => {
            const status = data[mod] || 'INACTIVO';
            const indicator = document.getElementById(`status-${mod}`);

            if (indicator) {
                if (status === 'ACTIVO') {
                    if (!indicator.classList.contains('active')) indicator.className = 'status-indicator active';
                } else if (status === 'INACTIVO') {
                    if (!indicator.classList.contains('inactive')) indicator.className = 'status-indicator inactive';
                } else {
                    if (!indicator.classList.contains('unknown')) indicator.className = 'status-indicator unknown';
                }
            }
        });

        // Update WAN specific info only if status changed or info is missing
        if (data.wan !== lastWanStatus || !lastWanConfig) {
            updateWanInfo(data.wan);
            lastWanStatus = data.wan;
        }
    } catch (e) {
        console.error("Error refreshing status:", e);
    }
}

async function updateWanInfo(status) {
    const infoBox = document.getElementById('wan-interface-info');
    if (!infoBox) return;

    if (status === 'ACTIVO') {
        try {
            // Fetch only if needed or force refresh
            const response = await fetch('/admin/config/wan/wan.json', { credentials: 'include' });
            const config = await response.json();

            // Only update DOM if configuration actually changed
            const configStr = JSON.stringify(config);
            if (configStr !== lastWanConfig) {
                document.getElementById('wan-interface').textContent = config.interface || 'eth0';
                document.getElementById('wan-mode').textContent = (config.mode || 'dhcp').toUpperCase();
                lastWanConfig = configStr;
            }
            infoBox.style.display = 'block';
        } catch (e) { infoBox.style.display = 'none'; }
    } else {
        infoBox.style.display = 'none';
        lastWanConfig = null;
    }
}

async function stopAllModules() {
    if (!confirm("⚠️ ADVERTENCIA: Esta acción detendrá TODOS los servicios de red. ¿Desea continuar?")) return;

    const msg = document.getElementById('stop-message');
    msg.textContent = "⌛ Deteniendo...";
    msg.style.color = "var(--warning)";

    const modules = ["wan", "nat", "firewall", "vlans", "tagging", "dmz", "ebtables"];
    let errors = 0;

    for (const mod of modules) {
        try {
            await fetch(`/admin/${mod}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'stop' }),
                credentials: 'include'
            });
        } catch (e) { errors++; }
    }

    msg.textContent = errors === 0 ? "✅ Sistema detenido" : `⚠️ Error en ${errors} módulos`;
    msg.style.color = errors === 0 ? "var(--success)" : "var(--error)";
    refreshStatus();
}

// --- INITIALIZATION ---
window.addEventListener('DOMContentLoaded', () => {
    // Initial status check
    refreshStatus();

    // Polling status every 5 seconds
    setInterval(refreshStatus, 5000);
});
