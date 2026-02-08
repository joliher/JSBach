async function refreshStatus() {
    const container = document.getElementById('statusContainer');
    const btn = document.getElementById('btnRefresh');

    btn.disabled = true;
    container.innerHTML = '<div class="loading">Cargando estado del firewall...</div>';

    try {
        // Si hay resultado de la última acción, mostrarlo primero
        try {
            const last = sessionStorage.getItem('firewallLastAction');
            if (last) {
                const parsed = JSON.parse(last);
                container.innerHTML = `\n<div class="info">Última acción: ${escapeHtml(parsed.action)} - ${escapeHtml(parsed.result && parsed.result.message ? parsed.result.message : '')}</div>`;
                // Limpiar para no mostrar repetidamente
                sessionStorage.removeItem('firewallLastAction');
            }
        } catch (e) {
            // ignore
        }

        const response = await fetch('/admin/firewall', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'status' }),
            credentials: 'include'
    });

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();

    if (data.success) {
        container.innerHTML = `
        <div class="success">✅ Estado obtenido correctamente</div>
        <pre class="status-content">${escapeHtml(data.message)}</pre>
        `;
    } else {
        container.innerHTML = `
        <div class="error">❌ Error: ${escapeHtml(data.message || 'Error desconocido')}</div>
        `;
    }
} catch (error) {
    console.error('Error:', error);
    container.innerHTML = `
    <div class="error">❌ Error al obtener el estado: ${escapeHtml(error.message)}</div>
    `;
} finally {
    btn.disabled = false;
}
}

function goBack() {
    if (parent && parent.frames['body']) {
        parent.frames['body'].location.href = '/web/firewall/info.html';
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Cargar estado al abrir la página
window.addEventListener('DOMContentLoaded', refreshStatus);