/* /web/modules/ebtables/js/config.js */

async function loadVlans() {
    const container = document.getElementById("vlan-container");
    container.innerHTML = '<div class="loading">Consultando configuración...</div>';

    try {
        // Get current PVLAN config
        const configResp = await fetch("/admin/config/ebtables/ebtables.json", { credentials: "include" });
        const config = await configResp.json();
        const pvlanConfig = config.pvlan || {};

        // Get actual VLANs list
        const vlansResp = await fetch("/admin/config/vlans/vlans.json", { credentials: "include" });
        const vData = await vlansResp.json();
        const vlans = vData.vlans || [];

        if (vlans.length === 0) {
            container.innerHTML = '<div class="info-box">No hay VLANs configuradas. Cree VLANs primero.</div>';
            return;
        }

        container.innerHTML = "";
        vlans.forEach(vlan => {
            if (vlan.id === 1 || vlan.id === 2) return; // Skip protected VLANs

            // Check isolation state from the ebtables.json structure: vlans -> id -> isolated
            const vlanConfig = (config.vlans && config.vlans[vlan.id.toString()]) || {};
            const isIsolated = vlanConfig.isolated === true;
            const card = document.createElement("div");
            card.className = "vlan-card";
            card.innerHTML = `
                <div class="vlan-info">
                    <h4>VLAN ${vlan.id}: ${vlan.name}</h4>
                    <p>Red: ${vlan.ip_network}</p>
                </div>
                <div class="vlan-action">
                    <button class="btn ${isIsolated ? 'btn-accent' : 'btn-blue'}" 
                            onclick="togglePvlan(${vlan.id}, ${!isIsolated})">
                        ${isIsolated ? '🛑 QUITAR AISLAMIENTO' : '🛡️ ACTIVAR AISLAMIENTO'}
                    </button>
                </div>
            `;
            container.appendChild(card);
        });
    } catch (err) {
        container.innerHTML = '<div class="warning-box">Error al cargar la configuración de VLANs.</div>';
    }
}

async function togglePvlan(vlanId, state) {
    const msg = document.getElementById("message-container");
    msg.textContent = "⏳ Procesando...";
    msg.style.color = "var(--text-secondary)";

    try {
        const action = state ? 'isolate' : 'unisolate';
        const response = await fetch("/admin/ebtables", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ action, params: { vlan_id: vlanId.toString() } })
        });
        const data = await response.json();
        if (data.success) {
            msg.textContent = "✅ " + data.message;
            msg.style.color = "var(--success)";
            loadVlans();
        } else {
            showToast("❌ Error: " + (data.message || data.detail || "Error desconocido")); msg.textContent = "";
            msg.style.color = "var(--error)";
        }
    } catch (err) {
        msg.textContent = "❌ Error de conexión";
    }
}

window.addEventListener('DOMContentLoaded', loadVlans);
