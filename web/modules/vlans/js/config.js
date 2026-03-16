/* /web/modules/vlans/js/config.js */

function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

let vlansCache = {};

async function loadVlans() {
    const tbody = document.querySelector("#vlansTable tbody");
    if (!tbody) return;

    try {
        const response = await fetch("/admin/config/vlans/vlans.json", { credentials: "include" });
        if (response.ok) {
            const data = await response.json();
            const vlans = (data.vlans || []).sort((a, b) => parseInt(a.id) - parseInt(b.id));
            tbody.innerHTML = "";
            vlansCache = {};

            if (vlans.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">No hay VLANs configuradas.</td></tr>';
                return;
            }

            vlans.forEach(vlan => {
                vlansCache[vlan.id] = vlan;
                const tr = document.createElement("tr");
                tr.dataset.id = vlan.id;
                renderVlanRow(tr, vlan);
                tbody.appendChild(tr);
            });
        }
    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="5" style="color:var(--error); text-align:center;">Error al cargar VLANs.</td></tr>';
    }
}

function renderVlanRow(tr, vlan) {
    const isProtected = (vlan.id === 1 || vlan.id === 2);
    tr.innerHTML = `
        <td><code>${vlan.id}</code></td>
        <td><b>${escapeHtml(vlan.name)}</b></td>
        <td>${escapeHtml(vlan.ip_interface)}</td>
        <td>${escapeHtml(vlan.ip_network)}</td>
        <td>
            <div class="action-group">
                <button class="btn btn-blue btn-small" onclick="editRow(${vlan.id})" title="Editar">✏️</button>
                ${isProtected ? '' : `<button class="btn btn-red btn-small" onclick="deleteVlan(${vlan.id})" title="Eliminar">🗑️</button>`}
            </div>
        </td>
    `;
}

function editRow(id) {
    const vlan = vlansCache[id];
    if (!vlan) return;
    const tr = document.querySelector(`tr[data-id="${id}"]`);
    if (!tr) return;

    tr.classList.add('edit-mode-row');
    tr.innerHTML = `
        <td><code>${vlan.id}</code></td>
        <td colspan="3">
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px;">
                <div class="table-form-group">
                    <label>Nombre</label>
                    <input type="text" class="inline-input" id="edit-name-${id}" value="${escapeHtml(vlan.name)}" required>
                </div>
                <div class="table-form-group">
                    <label>IP Interfaz</label>
                    <input type="text" class="inline-input" id="edit-ip-interface-${id}" value="${escapeHtml(vlan.ip_interface)}" required>
                </div>
                <div class="table-form-group">
                    <label>IP Red</label>
                    <input type="text" class="inline-input" id="edit-ip-network-${id}" value="${escapeHtml(vlan.ip_network)}" required>
                </div>
            </div>
        </td>
        <td>
            <div class="action-group">
                <button class="btn btn-green btn-small" onclick="saveInline(${id})" title="Guardar">💾</button>
                <button class="btn btn-red btn-small" onclick="cancelEdit(${id})" title="Cancelar">❌</button>
            </div>
        </td>
    `;
}

function cancelEdit(id) {
    const tr = document.querySelector(`tr[data-id="${id}"]`);
    const vlan = vlansCache[id];
    if (tr && vlan) {
        tr.classList.remove('edit-mode-row');
        renderVlanRow(tr, vlan);
    }
}

async function saveInline(id) {
    const name = document.getElementById(`edit-name-${id}`).value.trim();
    const ip_interface = document.getElementById(`edit-ip-interface-${id}`).value.trim();
    const ip_network = document.getElementById(`edit-ip-network-${id}`).value.trim();

    const resultDiv = document.getElementById("form-result");
    resultDiv.textContent = "⏳ Guardando...";
    resultDiv.style.color = "var(--text-secondary)";

    const params = { id, name, ip_interface, ip_network, action: "add" };

    try {
        const response = await fetch("/admin/vlans", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ action: "config", params })
        });
        const data = await response.json();
        if (data.success) {
            resultDiv.textContent = "✅ " + data.message;
            resultDiv.style.color = "var(--success)";
            loadVlans();
        } else {
            showToast("❌ Error: " + (data.message || data.detail || "Error desconocido"));
            resultDiv.textContent = "";
        }
    } catch (err) {
        resultDiv.textContent = "❌ Error de conexión";
        resultDiv.style.color = "var(--error)";
    }
}

async function deleteVlan(vlanId) {
    if (!confirm(`¿Eliminar VLAN ${vlanId}?`)) return;
    const resultDiv = document.getElementById("form-result");
    resultDiv.textContent = "⏳ Eliminando...";

    try {
        const response = await fetch("/admin/vlans", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ action: "config", params: { action: "remove", id: vlanId } })
        });
        const data = await response.json();
        if (data.success) {
            resultDiv.textContent = "✅ " + data.message;
            resultDiv.style.color = "var(--success)";
            loadVlans();
        } else {
            showToast("❌ Error: " + (data.message || data.detail || "Error desconocido")); resultDiv.textContent = "";
            resultDiv.style.color = "var(--error)";
        }
    } catch (err) {
        resultDiv.textContent = "❌ Error de conexión";
        resultDiv.style.color = "var(--error)";
    }
}

async function handleVlanSubmit(e) {
    e.preventDefault();
    const resultDiv = document.getElementById("form-result");
    resultDiv.textContent = "⏳ Guardando...";
    resultDiv.style.color = "var(--text-secondary)";

    const params = {
        id: parseInt(document.getElementById("vlan-id").value),
        name: document.getElementById("vlan-name").value,
        ip_interface: document.getElementById("vlan-ip-interface").value,
        ip_network: document.getElementById("vlan-ip-network").value
    };

    try {
        const response = await fetch("/admin/vlans", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ action: "config", params: { ...params, action: "add" } })
        });
        const data = await response.json();
        if (data.success) {
            resultDiv.textContent = "✅ " + data.message;
            resultDiv.style.color = "var(--success)";
            document.getElementById("vlan-form").reset();
            loadVlans();
        } else {
            showToast("❌ Error: " + (data.message || data.detail || "Error desconocido")); resultDiv.textContent = "";
            resultDiv.style.color = "var(--error)";
        }
    } catch (err) {
        resultDiv.textContent = "❌ Error de conexión";
        resultDiv.style.color = "var(--error)";
    }
}

window.addEventListener('DOMContentLoaded', () => {
    loadVlans();
    document.getElementById("vlan-form")?.addEventListener("submit", handleVlanSubmit);
});
