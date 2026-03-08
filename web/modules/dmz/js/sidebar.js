/* /web/modules/dmz/js/sidebar.js */

function irSeccion(page) {
    window.parent.location.href = `/web/modules/dmz/${page}.html`;
}

function irAccion(action) {
    window.parent.location.href = `/web/modules/dmz/status.html?action=${action}`;
}

async function loadLoggingStatus() {
    try {
        const response = await fetch('/admin/config/dmz/dmz.json', { credentials: 'include' });
        if (response.ok) {
            const cfg = await response.json();
            const toggle = document.getElementById('toggle-log');
            if (toggle) toggle.checked = !!cfg.traffic_log;
        }
    } catch (e) { }
}

// Polling for module status and dependencies
let lastStatus = '';
function fetchModuleStatus() {
    fetch('/admin/status', { credentials: 'include' })
        .then(response => response.json())
        .then(data => {
            const status = data['dmz'] || 'DESCONOCIDO';
            if (status !== lastStatus) {
                lastStatus = status;
                const statusBox = document.getElementById('module-status');
                if (statusBox) {
                    statusBox.textContent = `Estado: ${status}`;
                    statusBox.className = 'status-box ' + status.toLowerCase();
                }
            }

            const taggingStatus = data['tagging'] || 'DESCONOCIDO';
            const depTagging = document.getElementById('dep-tagging');
            if (depTagging) {
                if (taggingStatus === 'ACTIVO') {
                    depTagging.innerHTML = '✅ Tagging: Activo';
                    depTagging.style.color = 'var(--success)';
                } else {
                    depTagging.innerHTML = `❌ Tagging: ${taggingStatus}`;
                    depTagging.style.color = 'var(--error)';
                }
            }

            const firewallStatus = data['firewall'] || 'DESCONOCIDO';
            const depFirewall = document.getElementById('dep-firewall');
            if (depFirewall) {
                if (firewallStatus === 'ACTIVO') {
                    depFirewall.innerHTML = '✅ Firewall: Activo';
                    depFirewall.style.color = 'var(--success)';
                } else {
                    depFirewall.innerHTML = `❌ Firewall: ${firewallStatus}`;
                    depFirewall.style.color = 'var(--error)';
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
        'destinations': 'btnDestinations',
        'config': 'btnConfig',
        'info': 'btnInfo'
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

    if (!found && (path.endsWith('/dmz/') || path.endsWith('/dmz/index.html'))) {
        document.getElementById('btnStatus')?.classList.add('selected');
    }

    loadLoggingStatus();
    fetchModuleStatus();
});
