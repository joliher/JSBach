async function refreshStatus() {
    const container = document.getElementById('statusContainer');
    const btn = document.getElementById('btnRefresh');
    const actionResult = getLastActionResult();

    btn.disabled = true;
    container.innerHTML = '<div class="loading">Cargando estado de Tagging...</div>';

    try {
        const response = await fetch('/admin/tagging', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'status' }),
            credentials: 'include'
    });

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();

    const actionHtml = renderActionResult(actionResult);
    if (data.success) {
        container.innerHTML = `
        ${actionHtml}
        <div class="success">✅ Estado obtenido correctamente</div>
        <pre class="status-content">${escapeHtml(data.message)}</pre>
        `;
    } else {
        container.innerHTML = `
        ${actionHtml}
        <div class="error">❌ Error: ${escapeHtml(data.message || 'Error desconocido')}</div>
        `;
    }
} catch (error) {
    console.error('Error:', error);
    const actionHtml = renderActionResult(actionResult);
    container.innerHTML = `
    ${actionHtml}
    <div class="error">❌ Error al obtener el estado: ${escapeHtml(error.message)}</div>
    `;
} finally {
    btn.disabled = false;
}
}

function goBack() {
    if (parent && parent.frames['body']) {
        parent.frames['body'].location.href = '/web/tagging/info.html';
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function getLastActionResult() {
    const raw = sessionStorage.getItem('taggingLastActionResult');
    if (!raw) return null;
    sessionStorage.removeItem('taggingLastActionResult');
    try {
        return JSON.parse(raw);
    } catch (e) {
        return null;
    }
}

function renderActionResult(result) {
    if (!result) return '';
    const statusClass = result.success ? 'success' : 'error';
    const title = result.success ? '✅ Accion ejecutada' : '❌ Error ejecutando accion';
    const message = escapeHtml(result.message || 'Sin detalles');
    return `
    <div class="${statusClass}">${title}</div>
    <pre class="status-content">${message}</pre>
    `;
}

// Cargar estado al abrir la página
window.addEventListener('DOMContentLoaded', refreshStatus);