/* /web/js/utils.js */

/**
 * Muestra una notificación flotante (toast) en la esquina superior derecha.
 * @param {string} message - El mensaje a mostrar.
 * @param {string} type - El tipo de notificación ('error', 'success', 'info').
 */
function showToast(message, type = 'error') {
    // Buscar o crear el contenedor de toasts
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    // Crear el elemento toast
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    // Icono basado en el tipo
    let icon = '❌';
    if (type === 'success') {
        icon = '✅';
        toast.style.borderLeftColor = 'var(--success)';
    } else if (type === 'info') {
        icon = 'ℹ️';
        toast.style.borderLeftColor = '#3b82f6';
    }

    // Limpiar el mensaje si viene con el prefijo "❌ Error:"
    const cleanMessage = message.replace(/^❌\s*Error:\s*/i, '').trim();

    toast.innerHTML = `
        <div class="toast-icon">${icon}</div>
        <div class="toast-content">${cleanMessage}</div>
    `;

    // Cerrar al hacer clic
    toast.onclick = () => removeToast(toast);

    // Añadir al contenedor
    container.appendChild(toast);

    // Auto-eliminar después de 5 segundos
    setTimeout(() => {
        removeToast(toast);
    }, 5000);
}

function removeToast(toast) {
    if (toast.classList.contains('removing')) return;
    toast.classList.add('removing');
    toast.addEventListener('animationend', () => {
        toast.remove();
        // Eliminar el contenedor si está vacío
        const container = document.getElementById('toast-container');
        if (container && container.childNodes.length === 0) {
            // No lo eliminamos para evitar recrearlo constantemente, pero se podría
        }
    });
}

// Exposicion global para ser llamado desde cualquier script
window.showToast = showToast;
