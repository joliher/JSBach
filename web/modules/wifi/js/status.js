/* /web/modules/wifi/js/status.js */

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML.replace(/\n/g, '<br>');
}

async function runAction(action) {
    const container = document.getElementById('status-container');
    if (!container) return;

    container.innerHTML = `<div class="loading">⏳ Ejecutando acción: ${action.toUpperCase()}...</div>`;

    try {
        const response = await fetch('/admin/wifi', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action, params: {} }),
            credentials: 'include'
        });
        const data = await response.json();

        if (response.ok && data.success) {
            let statusColor = 'var(--success)';
            let statusIcon = '✅';

            if (data.message.includes('INCOMPATIBLE')) {
                statusColor = 'var(--error)';
                statusIcon = '⚠️';
            }

            container.innerHTML = `
                <div style="color: ${statusColor}; font-weight: 600; margin-bottom: 15px; font-size: 1.1rem;">${statusIcon} Operación completada</div>
                <div class="output-box" style="background: rgba(0,0,0,0.2); padding: 20px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05); font-family: 'Fira Code', monospace; line-height: 1.6;">
                    ${escapeHtml(data.message)}
                </div>
            `;

            if (data.message.includes('Módulo no compatible')) {
                container.innerHTML += `
                    <div style="margin-top: 20px; padding: 20px; background: rgba(239, 68, 68, 0.1); border-radius: 8px; border: 1px solid var(--error);">
                        <h4 style="color: #fca5a5; margin-top: 0;">🛑 Hardware No Soportado</h4>
                        <p style="color: var(--text-secondary); font-size: 0.9rem;">
                            Este dispositivo no dispone de una interfaz inalámbrica que soporte el modo <strong>Punto de Acceso (AP)</strong>. 
                            El módulo Wi-Fi ha sido deshabilitado automáticamente.
                        </p>
                    </div>
                `;
            }
        } else {
            const errorMsg = data.message || data.detail || 'Error desconocido';
            container.innerHTML = `
                <div style="color: var(--error); font-weight: 600; margin-bottom: 15px; font-size: 1.1rem;">❌ Error en la acción</div>
                <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.2); padding: 20px; border-radius: 8px; color: #fca5a5; font-family: 'Fira Code', monospace;">
                    ${escapeHtml(errorMsg)}
                </div>
            `;
        }
    } catch (error) {
        container.innerHTML = `<div style="color: var(--error); padding: 20px; text-align: center;">❌ Error de conexión al servidor</div>`;
    }
}

function fetchStatus() {
    runAction('status');
}

window.addEventListener('DOMContentLoaded', () => {
    const params = new URLSearchParams(window.location.search);
    const action = params.get('action') || 'status';
    runAction(action);
});
