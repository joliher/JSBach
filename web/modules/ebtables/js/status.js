/* /web/modules/ebtables/js/status.js */

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function runAction(action) {
    const container = document.getElementById('status-container');
    container.innerHTML = `<div class="loading">⏳ Ejecutando acción: ${action.toUpperCase()}...</div>`;

    try {
        const response = await fetch('/admin/ebtables', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action }),
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success) {
            container.innerHTML = `
                <div style="color: var(--success); font-weight: 600; margin-bottom: 10px;">✅ Acción completada con éxito</div>
                <div class="status-content">${escapeHtml(data.message)}</div>
            `;
        } else {
            container.innerHTML = `
                <div style="color: var(--error); font-weight: 600; margin-bottom: 10px;">❌ Error</div>
                <div class="status-content">${escapeHtml(data.message || 'Error desconocido')}</div>
            `;
        }
    } catch (error) {
        container.innerHTML = `<div style="color: var(--error);">❌ Error de conexión al servidor</div>`;
    }
}

async function refreshStatus() {
    runAction('status');
}

window.addEventListener('DOMContentLoaded', () => {
    const params = new URLSearchParams(window.location.search);
    const action = params.get('action') || 'status';
    runAction(action);
});
