/* /web/js/header.js - FIXED V4.2_REFRESH_01 */

function irSeccion(module) {
    // Redirigir al index.html del módulo dentro de la carpeta modules
    window.top.location.href = `/web/modules/${module}/index.html`;
}

async function logout() {
    // Eliminamos el confirm() nativo que puede ser bloqueado o fallar en iframes
    try {
        console.log("Logout triggered");
        const res = await fetch('/logout', { method: 'POST', credentials: 'include' });
        if (res.ok) {
            window.top.location.href = "/login";
        } else {
            console.error("Logout status:", res.status);
            // Fallback: redirección forzada
            window.top.location.href = "/login";
        }
    } catch (e) {
        console.error("Logout error", e);
        window.top.location.href = "/login";
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
    const modules = ["wan", "nat", "vlans", "tagging", "firewall", "dmz", "ebtables", "expect", "dhcp", "wifi", "security"];
    for (const mod of modules) {
        if (path.includes(`/modules/${mod}/`)) {
            updateActiveButton(mod);
            return;
        }
    }
});
