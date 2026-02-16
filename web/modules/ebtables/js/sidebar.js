/* /web/modules/ebtables/js/sidebar.js */

function irSeccion(page) {
    window.parent.location.href = `/web/modules/ebtables/${page}.html`;
}

function irAccion(action) {
    window.parent.location.href = `/web/modules/ebtables/status.html?action=${action}`;
}

// Polling for module status and dependencies
let lastStatus = '';
function fetchModuleStatus() {
    fetch('/admin/status', { credentials: 'include' })
        .then(response => response.json())
        .then(data => {
            // Module Status
            const status = data['ebtables'] || 'DESCONOCIDO';
            if (status !== lastStatus) {
                lastStatus = status;
                const statusBox = document.getElementById('module-status');
                if (statusBox) {
                    statusBox.textContent = `Estado: ${status}`;
                    statusBox.className = 'status-box ' + status.toLowerCase();
                }
            }

            // Dependency Mapping
            const deps = {
                'wan': 'dep-wan',
                'vlans': 'dep-vlans',
                'tagging': 'dep-tagging'
            };

            for (const [mod, elementId] of Object.entries(deps)) {
                const modStatus = data[mod] || 'DESCONOCIDO';
                const el = document.getElementById(elementId);
                if (el) {
                    if (modStatus === 'ACTIVO') {
                        el.innerHTML = `✅ ${mod.toUpperCase()}: Activo`;
                        el.style.color = 'var(--success)';
                    } else {
                        el.innerHTML = `❌ ${mod.toUpperCase()}: ${modStatus}`;
                        el.style.color = 'var(--error)';
                    }
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

    if (path.endsWith('/ebtables/') || path.endsWith('/ebtables/index.html')) {
        document.getElementById('btnStatus')?.classList.add('selected');
    }

    fetchModuleStatus();
});
