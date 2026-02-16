/* /web/modules/firewall/js/vlans.js */

async function loadVlansState() {
    const container = document.getElementById("vlans-content");
    container.innerHTML = '<div class="loading">Consultando políticas por VLAN...</div>';

    try {
        const response = await fetch("/admin/firewall", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ action: "get_vlans_state" })
        });
        const data = await response.json();

        if (data.success) {
            const states = data.message; // Assume list of objects
            let html = `<table>
                <thead>
                    <tr>
                        <th>VLAN ID</th>
                        <th>NOMBRE</th>
                        <th>AISLAMIENTO</th>
                        <th>RESTRICCIÓN ROUTER</th>
                    </tr>
                </thead>
                <tbody>`;

            states.forEach(s => {
                html += `<tr>
                    <td><code>${s.id}</code></td>
                    <td><b>${s.name}</b></td>
                    <td><span class="badge" style="background:${s.isolated ? 'rgba(239, 68, 68, 0.1); color:var(--error);' : 'rgba(16, 185, 129, 0.1); color:var(--success);'}">${s.isolated ? 'AISLADA' : 'ABIERTA'}</span></td>
                    <td><span class="badge" style="background:${s.restricted ? 'rgba(239, 68, 68, 0.1); color:var(--error);' : 'rgba(16, 185, 129, 0.1); color:var(--success);'}">${s.restricted ? 'RESTRINGIDO' : 'ACCESO'}</span></td>
                </tr>`;
            });
            html += `</tbody></table>`;
            container.innerHTML = html;
        } else {
            container.innerHTML = `<div class="warning-box">No hay datos disponibles: ${data.message}</div>`;
        }
    } catch (err) {
        container.innerHTML = '<div class="warning-box">Error al cargar el estado. Asegúrese de que el servicio VLANs esté iniciado.</div>';
    }
}

window.addEventListener('DOMContentLoaded', loadVlansState);
