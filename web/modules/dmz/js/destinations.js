/* /web/modules/dmz/js/destinations.js */

let dmzCache = [];

async function loadDestinations() {
    const tbody = document.querySelector("#destinationsTable tbody");
    tbody.innerHTML = '<tr><td colspan="5" class="loading">Cargando...</td></tr>';

    try {
        const response = await fetch("/admin/config/dmz/dmz.json", { credentials: "include" });
        if (response.ok) {
            const config = await response.json();
            const destinations = config.destinations || [];
            dmzCache = destinations;

            const statusResp = await fetch("/admin/status", { credentials: "include" });
            const sData = await statusResp.json();

            tbody.innerHTML = "";
            if (destinations.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">No hay destinos configurados.</td></tr>';
            } else {
                destinations.forEach((dest, index) => {
                    const tr = document.createElement("tr");
                    tr.dataset.index = index;
                    renderDestRow(tr, dest, index);
                    tbody.appendChild(tr);
                });
            }

            document.getElementById("wan-iface").textContent = config.wan_interface || 'No detectada';
            document.getElementById("vlans-state").textContent = sData.vlans || 'Inactivo';
        }
    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="5" style="color:var(--error); text-align:center;">Error al conectar con el servidor.</td></tr>';
    }
}

function renderDestRow(tr, dest, index) {
    const isIsolated = dest.isolated === true;
    tr.innerHTML = `
        <td><code>${escapeHtml(dest.ip)}</code></td>
        <td>${dest.port}</td>
        <td><span class="badge" style="background:rgba(255,255,255,0.05);">${dest.protocol.toUpperCase()}</span></td>
        <td><span class="badge ${isIsolated ? 'badge-inactive' : 'badge-active'}">${isIsolated ? 'AISLADO' : 'ACTIVO'}</span></td>
        <td>
            <div class="action-group">
                <button class="btn btn-blue btn-small" onclick="editRow(${index})" title="Editar">✏️</button>
                <button class="btn btn-small ${isIsolated ? 'btn-blue' : 'btn-red'}" 
                        style="background: ${isIsolated ? '#059669' : '#dc2626'};"
                        onclick="toggleIsolation('${dest.ip}', ${!isIsolated})">
                    ${isIsolated ? '🔓' : '🔒'}
                </button>
                <button class="btn btn-red btn-small" onclick="deleteDestination('${dest.ip}', ${dest.port}, '${dest.protocol}')" title="Eliminar">🗑️</button>
            </div>
        </td>
    `;
}

function editRow(index) {
    const dest = dmzCache[index];
    if (!dest) return;
    const tr = document.querySelector(`tr[data-index="${index}"]`);
    if (!tr) return;

    tr.classList.add('edit-mode-row');
    tr.innerHTML = `
        <td colspan="4">
            <div style="display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 10px;">
                <div class="table-form-group">
                    <label>IP de destino</label>
                    <input type="text" class="inline-input" id="edit-ip-${index}" value="${escapeHtml(dest.ip)}">
                </div>
                <div class="table-form-group">
                    <label>Puerto</label>
                    <input type="number" class="inline-input" id="edit-port-${index}" value="${dest.port}">
                </div>
                <div class="table-form-group">
                    <label>Protocolo</label>
                    <select id="edit-protocol-${index}" class="inline-input" style="height: 35px;">
                        <option value="tcp" ${dest.protocol === 'tcp' ? 'selected' : ''}>TCP</option>
                        <option value="udp" ${dest.protocol === 'udp' ? 'selected' : ''}>UDP</option>
                    </select>
                </div>
            </div>
        </td>
        <td>
            <div class="action-group" style="height: 100%; align-items: flex-end;">
                <button class="btn btn-green btn-small" onclick="saveInline(${index})" title="Guardar">💾</button>
                <button class="btn btn-red btn-small" onclick="cancelEdit(${index})" title="Cancelar">❌</button>
            </div>
        </td>
    `;
}

function cancelEdit(index) {
    const tr = document.querySelector(`tr[data-index="${index}"]`);
    const dest = dmzCache[index];
    if (tr && dest) {
        tr.classList.remove('edit-mode-row');
        renderDestRow(tr, dest, index);
    }
}

async function saveInline(index) {
    const old = dmzCache[index];
    const newIp = document.getElementById(`edit-ip-${index}`).value.trim();
    const newPort = parseInt(document.getElementById(`edit-port-${index}`).value);
    const newProtocol = document.getElementById(`edit-protocol-${index}`).value;

    try {
        const response = await fetch("/admin/dmz", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({
                action: "update_destination",
                params: {
                    old_ip: old.ip, old_port: old.port, old_protocol: old.protocol,
                    new_ip: newIp, new_port: newPort, new_protocol: newProtocol
                }
            })
        });
        const data = await response.json();
        if (data.success) {
            loadDestinations();
        } else {
            alert("❌ Error: " + (data.message || data.detail || "Error desconocido"));
        }
    } catch (err) {
        alert("❌ Error de comunicación");
    }
}

async function deleteDestination(ip, port, protocol) {
    if (!confirm(`¿Eliminar redirección DMZ para ${ip}:${port} (${protocol})?`)) return;

    try {
        const response = await fetch("/admin/dmz", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({
                action: "remove_destination",
                params: { ip, port, protocol }
            })
        });
        const data = await response.json();
        if (data.success) {
            loadDestinations();
        } else {
            showToast("❌ Error: " + (data.message || data.detail || "Error desconocido"));
        }
    } catch (err) {
        alert("Error de conexión");
    }
}

async function toggleIsolation(ip, shouldIsolate) {
    const action = shouldIsolate ? 'isolate' : 'unisolate';
    if (!confirm(`¿Estás seguro de ${shouldIsolate ? 'aislar' : 'desaislar'} el host ${ip}?`)) return;
    try {
        const resp = await fetch('/admin/dmz', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
            body: JSON.stringify({ action, params: { ip } })
        });
        if ((await resp.json()).success) loadDestinations();
    } catch (e) { }
}

window.addEventListener('DOMContentLoaded', loadDestinations);
