/* /web/modules/ebtables/js/config.js */

async function loadVlans() {
    const container = document.getElementById("vlan-container");
    container.innerHTML = '<div class="loading">Consultando configuración...</div>';

    try {
        // Get current PVLAN config
        const configResp = await fetch("/admin/config/ebtables/ebtables.json", { credentials: "include" });
        const config = await configResp.json();

        // Get actual VLANs list
        const vlansResp = await fetch("/admin/config/vlans/vlans.json", { credentials: "include" });
        const vData = await vlansResp.json();
        const vlans = vData.vlans || [];
        vlans.sort((a, b) => parseInt(a.id) - parseInt(b.id));

        container.innerHTML = "";

        // --- SECCIÓN VLANS ---
        vlans.forEach(vlan => {
            const vlanCfg = (config.vlans && config.vlans[vlan.id.toString()]) || {};
            renderCard(vlan.id, `VLAN ${vlan.id}: ${vlan.name}`, `Red: ${vlan.ip_network}`, vlanCfg, container);
        });

    } catch (err) {
        console.error(err);
        container.innerHTML = '<div class="warning-box">Error al cargar la configuración.</div>';
    }
}

function renderCard(id, title, subtitle, cfg, container) {
    const isIsolated = cfg.isolated === true;
    const isBlacklistEnabled = cfg.mac_blacklist_enabled === true;
    const blacklist = cfg.mac_blacklist || [];

    const card = document.createElement("div");
    card.className = "vlan-card";
    if (id === "wifi") card.style.borderLeft = "4px solid var(--accent)";

    card.innerHTML = `
        <div class="vlan-main">
            <div class="vlan-info" onclick="toggleBlacklistSection('${id}')">
                <h4>${title}</h4>
                <p>${subtitle}</p>
            </div>
            <div class="vlan-action">
                <button class="btn btn-sm ${isBlacklistEnabled ? 'btn-blue' : 'btn-outline'}" 
                        onclick="toggleBlacklist('${id}', ${!isBlacklistEnabled})">
                    ${isBlacklistEnabled ? '🛡️ Blacklist activa' : '⚙️ Blacklist inactiva'}
                </button>
                <button class="btn ${isIsolated ? 'btn-accent' : 'btn-blue'}" 
                        onclick="togglePvlan('${id}', ${!isIsolated})">
                    ${isIsolated ? '🛑 QUITAR AISLAMIENTO' : '🛡️ AISLAR'}
                </button>
            </div>
        </div>
        <div id="blacklist-section-${id}" class="blacklist-section ${isBlacklistEnabled ? 'active' : ''}">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <label style="font-weight: 600; font-size: 0.85rem; color: var(--text-secondary);">DISPOSITIVOS BLOQUEADOS (BLACKLIST)</label>
            </div>
            <ul class="mac-list">
                ${blacklist.map(mac => `
                    <li class="mac-item">
                        ${mac}
                        <span class="mac-remove" onclick="removeMac('${id}', '${mac}')" title="Eliminar">&times;</span>
                    </li>
                `).join('')}
                ${blacklist.length === 0 ? '<li style="color: var(--text-secondary); font-size: 0.8rem;">Sin dispositivos bloqueados</li>' : ''}
            </ul>
            <div class="mac-input-group">
                <input type="text" id="new-mac-${id}" placeholder="XX:XX:XX:XX:XX:XX" maxlength="17">
                <button class="btn btn-success btn-sm" onclick="addMac('${id}')">BLOQUEAR MAC</button>
            </div>
        </div>
    `;
    container.appendChild(card);
}

function toggleBlacklistSection(id) {
    const el = document.getElementById(`blacklist-section-${id}`);
    el.classList.toggle('active');
}

async function togglePvlan(vlanId, state) {
    return runBackendAction(state ? 'isolate' : 'unisolate', { vlan_id: vlanId });
}

async function toggleBlacklist(vlanId, state) {
    return runBackendAction(state ? 'enable_blacklist' : 'disable_blacklist', { vlan_id: vlanId });
}

async function addMac(vlanId) {
    const input = document.getElementById(`new-mac-${vlanId}`);
    const mac = input.value.trim();
    if (!mac) return;
    await runBackendAction('add_mac', { vlan_id: vlanId, mac: mac });
    input.value = "";
}

async function removeMac(vlanId, mac) {
    if (!confirm(`¿Desbloquear MAC ${mac}?`)) return;
    await runBackendAction('remove_mac', { vlan_id: vlanId, mac: mac });
}

async function runBackendAction(action, params) {
    const msg = document.getElementById("message-container");
    msg.textContent = "⏳ Procesando...";
    msg.style.color = "var(--text-secondary)";

    try {
        const response = await fetch("/admin/ebtables", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ action, params })
        });
        const data = await response.json();
        if (data.success) {
            showToast(data.message, 'success');
            msg.textContent = data.message;
            msg.style.color = "var(--success)";
            loadVlans();
        } else {
            showToast("❌ Error: " + (data.message || data.detail || "Error desconocido"));
            msg.textContent = "";
        }
    } catch (err) {
        msg.textContent = "❌ Error de conexión";
    }
}

window.addEventListener('DOMContentLoaded', loadVlans);
