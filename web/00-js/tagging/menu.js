function runTagging(event, action, btn) {
    // 🔒 Evitar que el botón navegue el iframe izquierdo
    event.preventDefault();
    event.stopPropagation();

    const iframe = parent.frames['body'];
    if (!iframe) {
        console.error("Iframe 'body' no encontrado");
        return;
    }

    // Marcar botón seleccionado
    const botones = document.querySelectorAll("button");
    botones.forEach(b => b.classList.remove("selected"));
    btn.classList.add("selected");

    sessionStorage.setItem("taggingSelected", btn.id);

    // Acción CONFIG → cargar config.html en iframe derecho
    if (action === "config") {
        iframe.location.href = "/web/tagging/config.html";
        return;
    }

    // Acciones START/STOP/RESTART/STATUS → cargar status.html para feedback
    if (action === "start" || action === "stop" || action === "restart" || action === "status") {
        iframe.location.href = "/web/tagging/status.html";
        // Ejecutar acción backend
        fetch('/admin/tagging', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action }),
            credentials: 'include'
        }).then(async response => {
            if (action === "status") return;
            let data = {};
            try {
                data = await response.json();
            } catch (e) {
                data = { success: false, message: "Respuesta invalida del servidor" };
            }

            if (!response.ok) {
                storeActionResult({
                    success: false,
                    message: data.detail || data.message || "Error desconocido"
                });
                return;
            }

            storeActionResult({
                success: Boolean(data.success),
                message: data.message || "Accion ejecutada"
            });
        }).catch(error => {
            if (action !== "status") {
                storeActionResult({ success: false, message: error.message });
            }
            console.error("Error al ejecutar la accion:", error);
        });
        return;
    }

// Otras acciones → mostrar info.html
iframe.location.href = "/web/tagging/info.html";
}

// Restaurar botón seleccionado
window.addEventListener("DOMContentLoaded", () => {
    const saved = sessionStorage.getItem("taggingSelected");
    if (saved) {
        const btn = document.getElementById(saved);
        if (btn) btn.classList.add("selected");
    }
    fetchModuleStatus();
});

// Función para obtener el estado del módulo con polling adaptativo
let lastStatus = '';
let pollInterval = 2000;
let unchangedCount = 0;
let statusTimerId = null;

function fetchModuleStatus() {
    fetch('/admin/status', { credentials: 'include' })
    .then(response => response.json())
    .then(data => {
        const status = data['tagging'] || 'DESCONOCIDO';

        if (status === lastStatus) {
            unchangedCount++;
            if (unchangedCount > 3) pollInterval = 5000;
            if (unchangedCount > 10) pollInterval = 10000;
            if (unchangedCount > 20) pollInterval = 30000;
        } else {
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

        clearTimeout(statusTimerId);
        statusTimerId = setTimeout(fetchModuleStatus, pollInterval);
    })
    .catch(error => {
        console.error('Error al obtener estado:', error);
        clearTimeout(statusTimerId);
        statusTimerId = setTimeout(fetchModuleStatus, 5000);
    });
}

function openInfo(event, btn) {
    event.preventDefault();
    event.stopPropagation();

    const iframe = parent.frames['body'];
    if (!iframe) return;

    document.querySelectorAll("button").forEach(b => b.classList.remove("selected"));
    btn.classList.add("selected");
    sessionStorage.setItem("taggingSelected", btn.id);

    iframe.location.href = "/web/tagging/info.html";
}

async function checkDependencies() {
    // Verificar VLANs
    const btnStart = document.getElementById('btnStart');
    try {
        const statusResp = await fetch('/admin/status', { credentials: 'include' });
        const statusData = await statusResp.json();
        const vlansDiv = document.getElementById('dep-vlans');
        const vlansStatus = statusData['vlans'] || 'DESCONOCIDO';
        if (vlansStatus === 'ACTIVO') {
            vlansDiv.innerHTML = '✅ VLANs: Activo';
            vlansDiv.style.color = '#155724';
            // Habilitar botón START
            btnStart.disabled = false;
            btnStart.title = '';
        } else {
            vlansDiv.innerHTML = '❌ VLANs: Inactivo (Requerido)';
            vlansDiv.style.color = '#721c24';
            // Deshabilitar botón START
            btnStart.disabled = true;
            btnStart.title = 'VLANs debe estar activo primero';
        }
    } catch {
        document.getElementById('dep-vlans').innerHTML = '⚠️ VLANs: Error al verificar';
        // Deshabilitar botón START por error
        btnStart.disabled = true;
        btnStart.title = 'Error al verificar dependencias';
    }
}

function storeActionResult(result) {
    sessionStorage.setItem("taggingLastActionResult", JSON.stringify(result));
}

// Verificar dependencias al cargar
window.addEventListener("DOMContentLoaded", () => {
    checkDependencies();
    // Actualizar dependencias cada 5 segundos
    setInterval(checkDependencies, 5000);
});