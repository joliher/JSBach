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
                        <th>ID / TIPO</th>
                        <th>NOMBRE</th>
                        <th>AISLAMIENTO LOCAL</th>
                        <th>RESTRICCIÓN ROUTER</th>
                    </tr>
                </thead>
                <tbody>`;

            states.forEach(s => {
                if (s.type === "wifi") return; // Omitimos Wi-Fi, centralizado en web/modules/wifi/

                let rowStyle = "";
                let nameExtra = "";
                // Celdas base (estilo badge JSBach)
                let isoStyle = s.isolated ? 'rgba(239, 68, 68, 0.15); color:var(--error); border: 1px solid rgba(239, 68, 68, 0.3);' : 'rgba(16, 185, 129, 0.15); color:var(--success); border: 1px solid rgba(16, 185, 129, 0.3);';
                let resStyle = s.restricted ? 'rgba(239, 68, 68, 0.15); color:var(--error); border: 1px solid rgba(239, 68, 68, 0.3);' : 'rgba(16, 185, 129, 0.15); color:var(--success); border: 1px solid rgba(16, 185, 129, 0.3);';

                let isoLabel = s.isolated ? 'AISLADA' : 'ABIERTA';
                let resLabel = s.restricted ? 'RESTRINGIDO' : 'ACCESO';

                let isolatedCell = `<span class="badge" style="${isoStyle}">${isoLabel}</span>`;
                let restrictedCell = `<span class="badge" style="${resStyle}">${resLabel}</span>`;

                html += `<tr style="${rowStyle}">
                    <td><code>${s.id}</code></td>
                    <td>
                        <b>${s.name}</b>
                        ${nameExtra}
                    </td>
                    <td>${isolatedCell}</td>
                    <td>${restrictedCell}</td>
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
