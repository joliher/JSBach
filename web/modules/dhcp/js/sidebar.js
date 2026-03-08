/* /web/modules/dhcp/js/sidebar.js */

function irSeccion(page) {
    window.parent.location.href = `/web/modules/dhcp/${page}.html`;
}

function irAccion(action) {
    window.parent.location.href = `/web/modules/dhcp/status.html?action=${action}`;
}

async function loadLoggingStatus() {
    try {
        const response = await fetch('/admin/config/dhcp/dhcp.json', { credentials: 'include' });
        if (response.ok) {
            const cfg = await response.json();
            const toggle = document.getElementById('toggle-log');
            if (toggle) toggle.checked = !!cfg.traffic_log_enabled;
        }
    } catch (e) { }
}

// Polling for module status box
let lastStatus = '';
function fetchModuleStatus() {
    fetch('/admin/status', { credentials: 'include' })
        .then(response => response.json())
        .then(data => {
            const status = data['dhcp'] || 'DESCONOCIDO';
            if (status !== lastStatus) {
                lastStatus = status;
                const statusBox = document.getElementById('module-status');
                if (statusBox) {
                    statusBox.textContent = `Estado: ${status}`;
                    statusBox.className = 'status-box ' + status.toLowerCase();
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

    // Quitar 'selected' de todos los botones primero
    document.querySelectorAll('button').forEach(btn => btn.classList.remove('selected'));

    const pages = {
        'config': 'btnConfig',
        'info': 'btnInfo',
        'leases': 'btnLeases'
    };

    let found = false;
    for (const [page, btnId] of Object.entries(pages)) {
        if (path.indexOf('/' + page + '.html') !== -1) {
            document.getElementById(btnId)?.classList.add('selected');
            found = true;
        }
    }

    if (!found && path.includes('/status.html')) {
        const params = new URLSearchParams(search);
        const action = params.get('action') || 'status';
        const actionBtns = {
            'start': 'btnStart',
            'stop': 'btnStop',
            'restart': 'btnRestart',
            'status': 'btnStatus'
        };
        document.getElementById(actionBtns[action] || 'btnStatus')?.classList.add('selected');
    }

    if (!found && (path.endsWith('/dhcp/') || path.endsWith('/dhcp/index.html'))) {
        document.getElementById('btnStatus')?.classList.add('selected');
    }

    loadLoggingStatus();
    fetchModuleStatus();
});
