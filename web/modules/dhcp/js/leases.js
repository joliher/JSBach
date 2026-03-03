/* /web/modules/dhcp/js/leases.js */

async function fetchLeases() {
    const tbody = document.getElementById('leases-body');
    tbody.innerHTML = '<tr><td colspan="4" class="loading">⏳ Consultando servidor...</td></tr>';

    try {
        const response = await fetch('/admin/dhcp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'list_leases' }),
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success) {
            const leases = data.message;
            if (leases.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 20px; color: var(--text-secondary);">No hay concesiones activas en este momento.</td></tr>';
                return;
            }

            let html = '';
            leases.forEach(lease => {
                html += `
                    <tr>
                        <td><code style="color: var(--accent); font-weight: 600;">${lease.ip}</code></td>
                        <td><code>${lease.mac}</code></td>
                        <td><b style="color: var(--text-main);">${lease.hostname}</b></td>
                        <td style="font-size: 0.85rem; opacity: 0.7;">${lease.client_id}</td>
                    </tr>
                `;
            });
            tbody.innerHTML = html;
        } else {
            tbody.innerHTML = `<tr><td colspan="4" class="error">❌ Error: ${data.message}</td></tr>`;
        }
    } catch (error) {
        tbody.innerHTML = '<tr><td colspan="4" class="error">❌ Error de conexión con el servidor.</td></tr>';
    }
}

window.addEventListener('DOMContentLoaded', fetchLeases);
