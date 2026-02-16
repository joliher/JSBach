/* /web/modules/tagging/js/sidebar.js */

function irSeccion(page) {
    window.parent.location.href = `/web/modules/tagging/${page}.html`;
}

function irAccion(action) {
    window.parent.location.href = `/web/modules/tagging/status.html?action=${action}`;
}

// Polling for module status and dependencies
let lastStatus = '';
function fetchModuleStatus() {
    fetch('/admin/status', { credentials: 'include' })
        .then(response => response.json())
        .then(data => {
            // Module Status
            const status = data['tagging'] || 'DESCONOCIDO';
            if (status !== lastStatus) {
                lastStatus = status;
                const statusBox = document.getElementById('module-status');
                if (statusBox) {
                    statusBox.textContent = `Estado: ${status}`;
                    statusBox.className = 'status-box ' + status.toLowerCase();
                }
            }

            // VLANs Dependency
            const vlansStatus = data['vlans'] || 'DESCONOCIDO';
            const depVlans = document.getElementById('dep-vlans');
            if (depVlans) {
                if (vlansStatus === 'ACTIVO') {
                    depVlans.innerHTML = '✅ VLANs: Activo';
                    depVlans.style.color = 'var(--success)';
                } else {
                    depVlans.innerHTML = `❌ VLANs: ${vlansStatus}`;
                    depVlans.style.color = 'var(--error)';
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

    if (path.endsWith('/tagging/') || path.endsWith('/tagging/index.html')) {
        document.getElementById('btnStatus')?.classList.add('selected');
    }

    fetchModuleStatus();
});
