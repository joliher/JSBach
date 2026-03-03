function irSeccion(page) {
    window.parent.location.href = `/web/modules/wifi/${page}.html`;
}

function irAccion(action) {
    window.parent.location.href = `/web/modules/wifi/status.html?action=${action}`;
}

let lastStatus = '';
function fetchModuleStatus() {
    fetch('/admin/status', { credentials: 'include' })
        .then(response => response.json())
        .then(data => {
            let status = data['wifi'] || 'DESCONOCIDO';
            if (status !== lastStatus) {
                lastStatus = status;
                const statusBox = document.getElementById('module-status');
                if (statusBox) {
                    statusBox.textContent = `Estado: ${status}`;
                    // Limpiar clases previas y añadir la nueva basada en la primera palabra (ej: ACTIVO (PID...) -> activo)
                    const statusClass = status.split(' ')[0].toLowerCase();
                    statusBox.className = 'status-box ' + statusClass;
                }
            }
            setTimeout(fetchModuleStatus, 5000);
        })
        .catch(() => {
            setTimeout(fetchModuleStatus, 5000);
        });
}

window.addEventListener('DOMContentLoaded', () => {
    const path = window.parent.location.pathname;
    const search = window.parent.location.search;

    const pages = {
        'config': 'btnConfig',
        'security_config': 'btnSecurity',
        'portal_config': 'btnPortal',
        'info': 'btnInfo'
    };

    for (const [page, btnId] of Object.entries(pages)) {
        if (path.endsWith(`/${page}.html`)) {
            const btn = document.getElementById(btnId);
            if (btn) btn.classList.add('selected');
        }
    }

    if (path.includes('/status.html')) {
        const params = new URLSearchParams(search);
        const action = params.get('action') || 'status';
        const actionBtns = {
            'start': 'btnStart',
            'stop': 'btnStop',
            'restart': 'btnRestart',
            'status': 'btnStatus'
        };
        const btn = document.getElementById(actionBtns[action] || 'btnStatus');
        if (btn) btn.classList.add('selected');
    }

    fetchModuleStatus();
});
