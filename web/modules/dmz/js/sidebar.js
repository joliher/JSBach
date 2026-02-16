/* /web/modules/dmz/js/sidebar.js */

function irSeccion(page) {
    window.parent.location.href = `/web/modules/dmz/${page}.html`;
}

function irAccion(action) {
    window.parent.location.href = `/web/modules/dmz/status.html?action=${action}`;
}

// Polling for module status and dependencies
let lastStatus = '';
function fetchModuleStatus() {
    fetch('/admin/status', { credentials: 'include' })
        .then(response => response.json())
        .then(data => {
            // Module Status
            const status = data['dmz'] || 'DESCONOCIDO';
            if (status !== lastStatus) {
                lastStatus = status;
                const statusBox = document.getElementById('module-status');
                if (statusBox) {
                    statusBox.textContent = `Estado: ${status}`;
                    statusBox.className = 'status-box ' + status.toLowerCase();
                }
            }

            // Tagging Dependency
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

            // Firewall Dependency
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

    const pages = {
        'destinations': 'btnDestinations',
        'config': 'btnConfig',
        'info': 'btnInfo'
    };

    for (const [page, btnId] of Object.entries(pages)) {
        if (path.includes(`/${page}.html`)) {
            document.getElementById(btnId)?.classList.add('selected');
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
        document.getElementById(actionBtns[action] || 'btnStatus')?.classList.add('selected');
    }

    if (path.endsWith('/dmz/') || path.endsWith('/dmz/index.html')) {
        document.getElementById('btnStatus')?.classList.add('selected');
    }

    fetchModuleStatus();
});
