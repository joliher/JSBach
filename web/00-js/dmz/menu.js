function openPage(page, btn) {
    const iframe = parent.frames['body'];

    // Resaltar botón seleccionado
    document.querySelectorAll("button").forEach(b => b.classList.remove("selected"));
    btn.classList.add("selected");
    sessionStorage.setItem("dmzSelected", btn.id);

    iframe.location.href = `/web/dmz/${page}.html`;
}

function executeAction(action, btn) {
    const iframe = parent.frames['body'];

    // Resaltar botón seleccionado
    document.querySelectorAll("button").forEach(b => b.classList.remove("selected"));
    btn.classList.add("selected");
    sessionStorage.setItem("dmzSelected", btn.id);

    // START/STOP/RESTART/STATUS → cargar status.html para feedback
    if (action === 'start' || action === 'stop' || action === 'restart' || action === 'status') {
        iframe.location.href = "/web/dmz/status.html";
    } else {
        // Otras acciones → mostrar info.html
        iframe.location.href = "/web/dmz/info.html";
    }

    // Ejecutar acción en segundo plano
    // ...

    fetch('/admin/dmz', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ action: action })
    })
        .then(response => {
            // ...
            return response.json();
        })
        .then(data => {
            // ...
        })
        .catch(error => {
            console.error('DMZ: Error ejecutando acción:', error);
        });
}

// Restaurar el botón seleccionado al cargar la página
window.onload = function () {
    const selected = sessionStorage.getItem("dmzSelected");
    if (selected) {
        const btn = document.getElementById(selected);
        if (btn) btn.classList.add("selected");
    }
    fetchModuleStatus();
};

// Variables para polling adaptativo
let lastStatus = null;
let unchangedCount = 0;
let pollInterval = 2000;
let statusTimerId = null;

function fetchModuleStatus() {
    fetch('/admin/status', { credentials: 'include' })
        .then(response => response.json())
        .then(data => {
            const status = data['dmz'] || 'DESCONOCIDO';

            // Actualizar UI de estado con polling adaptativo
            if (status === lastStatus) {
                // Si no cambió, ralentizar gradualmente
                unchangedCount++;
                if (unchangedCount > 3) pollInterval = 5000;   // Después de 3 = 5s
                if (unchangedCount > 10) pollInterval = 10000; // Después de 10 = 10s
                if (unchangedCount > 20) pollInterval = 30000; // Después de 20 = 30s
            } else {
                // Si cambió, volver a polling rápido y actualizar UI
                lastStatus = status;
                unchangedCount = 0;
                pollInterval = 2000;

                const statusBox = document.getElementById('module-status');
                statusBox.textContent = `Estado: ${status}`;
                statusBox.classList.remove('activo', 'inactivo', 'desconocido');

                if (status === 'ACTIVO') {
                    statusBox.classList.add('activo');
                } else if (status === 'INACTIVO') {
                    statusBox.classList.add('inactivo');
                } else {
                    statusBox.classList.add('desconocido');
                }
            }

            // Re-programar con el nuevo intervalo
            clearTimeout(statusTimerId);
            statusTimerId = setTimeout(fetchModuleStatus, pollInterval);
        })
        .catch(error => {
            console.error('Error al obtener estado:', error);
            clearTimeout(statusTimerId);
            statusTimerId = setTimeout(fetchModuleStatus, 5000); // Retry en 5s
        });
}

async function checkDependencies() {
    // Verificar Tagging y Firewall
    const btnStart = document.getElementById('btnStart');
    let taggingReady = false;
    let firewallReady = false;

    // Verificar Tagging
    try {
        const taggingResp = await fetch('/admin/tagging/info', { credentials: 'include' });
        const taggingData = await taggingResp.json();
        const taggingDiv = document.getElementById('dep-tagging');
        if (taggingData.status === 1) {
            taggingDiv.innerHTML = '✅ Tagging: Activo';
            taggingDiv.style.color = '#155724';
            taggingReady = true;
        } else {
            taggingDiv.innerHTML = '❌ Tagging: Inactivo (Requerido)';
            taggingDiv.style.color = '#721c24';
        }
    } catch {
        const taggingDiv = document.getElementById('dep-tagging');
        if (taggingDiv) {
            taggingDiv.innerHTML = '⚠️ Tagging: Error al verificar';
        }
    }

    // Verificar Firewall
    try {
        const firewallResp = await fetch('/admin/firewall/info', { credentials: 'include' });
        const firewallData = await firewallResp.json();
        const firewallDiv = document.getElementById('dep-firewall');
        if (firewallData.status === 1) {
            firewallDiv.innerHTML = '✅ Firewall: Activo';
            firewallDiv.style.color = '#155724';
            firewallReady = true;
        } else {
            firewallDiv.innerHTML = '❌ Firewall: Inactivo (Requerido)';
            firewallDiv.style.color = '#721c24';
        }
    } catch {
        const firewallDiv = document.getElementById('dep-firewall');
        if (firewallDiv) {
            firewallDiv.innerHTML = '⚠️ Firewall: Error al verificar';
        }
    }

    // Habilitar/Deshabilitar botón START
    if (taggingReady && firewallReady) {
        btnStart.disabled = false;
        btnStart.title = '';
    } else {
        btnStart.disabled = true;
        let reasons = [];
        if (!taggingReady) reasons.push("Tagging");
        if (!firewallReady) reasons.push("Firewall");
        btnStart.title = `${reasons.join(' y ')} debe(n) estar activo(s) primero`;
    }
}

// Verificar dependencias al cargar
window.addEventListener("DOMContentLoaded", () => {
    checkDependencies();
    // Actualizar dependencias cada 5 segundos
    setInterval(checkDependencies, 5000);
});