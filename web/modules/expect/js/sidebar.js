/* /web/modules/expect/js/sidebar.js */

function irSeccion(page) {
    // Redirigir la ventana padre (donde están las secciones)
    window.parent.location.href = `/web/modules/expect/${page}.html`;
}

// Auto-detectar sección activa basándose en la URL de la ventana superior
window.addEventListener('DOMContentLoaded', () => {
    const path = window.parent.location.pathname;
    const pages = {
        'switches': 'btnSwitches',
        'config': 'btnConfig',
        'security': 'btnSecurity',
        'info': 'btnInfo'
    };

    for (const [page, btnId] of Object.entries(pages)) {
        if (path.includes(`/${page}.html`)) {
            document.getElementById(btnId)?.classList.add('selected');
            break;
        }
    }

    // Si estamos en el index.html original del módulo, marcar switches por defecto
    if (path.endsWith('/expect/') || path.endsWith('/expect/index.html')) {
        document.getElementById('btnSwitches')?.classList.add('selected');
    }
});
