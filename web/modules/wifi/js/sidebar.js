function irSeccion(page) {
    window.parent.location.href = `/web/modules/wifi/${page}.html`;
}

function irAccion(action) {
    window.parent.location.href = `/web/modules/wifi/status.html?action=${action}`;
}

async function loadLoggingStatus() {
    try {
        const response = await fetch('/admin/config/wifi/wifi.json', { credentials: 'include' });
        if (response.ok) {
            const cfg = await response.json();
            const toggle = document.getElementById('toggle-log');
            if (toggle) toggle.checked = !!cfg.traffic_log;
        }
    } catch (e) { }
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

    document.querySelectorAll('button').forEach(btn => btn.classList.remove('selected'));

    const pages = {
        'config': 'btnConfig',
        'security_config': 'btnSecurity',
        'portal_config': 'btnPortal',
        'info': 'btnInfo'
    };

    let found = false;
    for (const [page, btnId] of Object.entries(pages)) {
        if (path.indexOf('/' + page + '.html') !== -1) {
            const btn = document.getElementById(btnId);
            if (btn) {
                btn.classList.add('selected');
                found = true;
            }
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

    if (!found && (path.endsWith('/wifi/') || path.endsWith('/wifi/index.html'))) {
        document.getElementById('btnStatus')?.classList.add('selected');
    }

    loadLoggingStatus();
    fetchModuleStatus();
});
