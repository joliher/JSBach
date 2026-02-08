let statusCheckInterval;

async function runEbtables(evt, action, btn) {
    evt.preventDefault();
    evt.stopPropagation();

    // Marcar botón seleccionado
    document.querySelectorAll('button').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    sessionStorage.setItem('ebtablesSelected', btn.id);

    const iframe = parent.frames['body'];
    if (action === "start" || action === "stop" || action === "restart" || action === "status") {
        try {
            const resp = await fetch('/admin/ebtables', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: action }),
                credentials: 'include'
            });

            let data = { success: false, message: 'Sin respuesta' };
            try {
                data = await resp.json();
            } catch (e) {
                data = { success: false, message: 'Respuesta invalida del servidor' };
            }

            if (action !== "status") {
                storeActionResult({
                    success: Boolean(data.success),
                    message: data.message || 'Accion ejecutada'
                });
            }
        } catch (error) {
            if (action !== "status") {
                storeActionResult({ success: false, message: error.message });
            }
            console.error('Error:', error);
        }

        iframe.location.href = "/web/ebtables/status.html";
    }
}

function goConfig(evt, btn) {
    evt.preventDefault();
    document.querySelectorAll('button').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    parent.frames['body'].location.href = "/web/ebtables/config.html";
}

function goInfo(evt, btn) {
    evt.preventDefault();
    document.querySelectorAll('button').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    parent.frames['body'].location.href = "/web/ebtables/info.html";
}

async function checkModuleStatus() {
    try {
        const response = await fetch('/admin/status', { credentials: 'include' });
        const data = await response.json();
        const status = data['ebtables'] || 'DESCONOCIDO';

        const statusBox = document.getElementById('module-status');
        statusBox.textContent = `Estado: ${status}`;
        statusBox.className = 'status-box';

        if (status === 'ACTIVO') {
            statusBox.classList.add('activo');
        } else if (status === 'INACTIVO') {
            statusBox.classList.add('inactivo');
        } else {
            statusBox.classList.add('desconocido');
        }
    } catch (error) {
        document.getElementById('module-status').textContent = 'Estado: DESCONOCIDO';
        document.getElementById('module-status').className = 'status-box desconocido';
    }
}

async function checkDependencies() {
    const btnStart = document.getElementById('btnStart');
    let wanReady = false;
    let vlansReady = false;
    let taggingReady = false;

    try {
        const statusResp = await fetch('/admin/status', { credentials: 'include' });
        const statusData = await statusResp.json();

        const wanDiv = document.getElementById('dep-wan');
        const wanStatus = statusData['wan'] || 'DESCONOCIDO';
        if (wanStatus === 'ACTIVO') {
            wanDiv.innerHTML = '✅ WAN: Activo';
            wanDiv.style.color = '#155724';
            wanReady = true;
        } else {
            wanDiv.innerHTML = '❌ WAN: Inactivo';
            wanDiv.style.color = '#721c24';
        }

        const vlansDiv = document.getElementById('dep-vlans');
        const vlansStatus = statusData['vlans'] || 'DESCONOCIDO';
        if (vlansStatus === 'ACTIVO') {
            vlansDiv.innerHTML = '✅ VLANs: Activo';
            vlansDiv.style.color = '#155724';
            vlansReady = true;
        } else {
            vlansDiv.innerHTML = '❌ VLANs: Inactivo';
            vlansDiv.style.color = '#721c24';
        }

        const taggingDiv = document.getElementById('dep-tagging');
        const taggingStatus = statusData['tagging'] || 'DESCONOCIDO';
        if (taggingStatus === 'ACTIVO') {
            taggingDiv.innerHTML = '✅ Tagging: Activo';
            taggingDiv.style.color = '#155724';
            taggingReady = true;
        } else {
            taggingDiv.innerHTML = '❌ Tagging: Inactivo';
            taggingDiv.style.color = '#721c24';
        }
    } catch {
        document.getElementById('dep-wan').innerHTML = '⚠️ WAN: Error al verificar';
        document.getElementById('dep-vlans').innerHTML = '⚠️ VLANs: Error al verificar';
        document.getElementById('dep-tagging').innerHTML = '⚠️ Tagging: Error al verificar';
    }

    // Habilitar/Deshabilitar botón START
    if (wanReady && vlansReady && taggingReady) {
        btnStart.disabled = false;
        btnStart.title = '';
    } else {
        btnStart.disabled = true;
        let reasons = [];
        if (!wanReady) reasons.push("WAN");
        if (!vlansReady) reasons.push("VLANs");
        if (!taggingReady) reasons.push("Tagging");
        btnStart.title = `${reasons.join(', ')} debe(n) estar activo(s) primero`;
    }
}

function storeActionResult(result) {
    sessionStorage.setItem('ebtablesLastActionResult', JSON.stringify(result));
}

/* -----------------------------
Inicialización cuando el DOM está listo
----------------------------- */

document.addEventListener("DOMContentLoaded", function () {
    const saved = sessionStorage.getItem('ebtablesSelected');
    if (saved) {
        const btn = document.getElementById(saved);
        if (btn) btn.classList.add('selected');
    }
    // Verificar estado inicial
    checkModuleStatus();
    checkDependencies();

    // Actualizar estado cada 5 segundos
    statusCheckInterval = setInterval(() => {
        checkModuleStatus();
        checkDependencies();
    }, 5000);

    // Limpiar intervalo al salir
    window.addEventListener('beforeunload', () => {
        if (statusCheckInterval) clearInterval(statusCheckInterval);
    });
});