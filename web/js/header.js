/* /web/js/header.js */

function irSeccion(module) {
    // Redirigir al index.html del módulo dentro de la carpeta modules
    window.top.location.href = `/web/modules/${module}/index.html`;
}

async function logout() {
    if (!confirm("¿Cerrar sesión?")) return;
    try {
        await fetch('/logout', { method: 'POST', credentials: 'include' });
        window.top.location.href = "/login";
    } catch (e) {
        console.error("Error logging out", e);
    }
}

// Para usar desde el index.html root (si fuera necesario)
function updateActiveButton(action) {
    document.querySelectorAll('.button-container button').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.action === action);
    });
}

// Auto-detectar sección activa basándose en la URL
window.addEventListener('DOMContentLoaded', () => {
    const path = window.top.location.pathname;
    const modules = ["wan", "nat", "vlans", "tagging", "firewall", "dmz", "ebtables", "expect"];
    for (const mod of modules) {
        if (path.includes(`/modules/${mod}/`)) {
            updateActiveButton(mod);
            return;
        }
    }
});
