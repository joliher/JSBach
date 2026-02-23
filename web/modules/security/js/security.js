/* /web/js/security.js */

async function checkMfaStatus() {
    try {
        const resp = await fetch('/admin/security/mfa/status');
        const data = await resp.json();

        const badge = document.getElementById('mfa-badge');
        const btnEnable = document.getElementById('btn-enable');
        const btnDisable = document.getElementById('btn-disable');

        if (data.enabled) {
            badge.textContent = "Activado";
            badge.className = "status-badge status-on";
            btnEnable.style.display = 'none';
            btnDisable.style.display = 'block';
        } else {
            badge.textContent = "Desactivado";
            badge.className = "status-badge status-off";
            btnEnable.style.display = 'block';
            btnDisable.style.display = 'none';
        }
    } catch (e) {
        console.error("Error checking MFA status", e);
    }
}

async function startMfaSetup() {
    try {
        const resp = await fetch('/admin/security/mfa/setup', { method: 'POST' });
        const data = await resp.json();

        document.getElementById('qr-container').innerHTML = `<img src="data:image/png;base64,${data.qr_code}" alt="QR Code">`;
        document.getElementById('mfa-secret-text').textContent = data.secret;

        document.getElementById('mfa-actions').style.display = 'none';
        document.getElementById('setup-area').style.display = 'block';
        document.getElementById('disable-area').style.display = 'none';
    } catch (e) {
        alert("Error al iniciar configuración de MFA");
    }
}

async function confirmEnableMfa() {
    const code = document.getElementById('verify-code').value;
    if (code.length !== 6) {
        alert("Ingrese un código de 6 dígitos");
        return;
    }

    try {
        const resp = await fetch('/admin/security/mfa/enable', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code })
        });

        if (resp.ok) {
            alert("MFA activado con éxito");
            location.reload();
        } else {
            const data = await resp.json();
            alert("Error: " + (data.detail || "Código incorrecto"));
        }
    } catch (e) {
        alert("Error de conexión");
    }
}

function showDisableArea() {
    document.getElementById('mfa-actions').style.display = 'none';
    document.getElementById('setup-area').style.display = 'none';
    document.getElementById('disable-area').style.display = 'block';
}

async function confirmDisableMfa() {
    const code = document.getElementById('disable-code').value;
    try {
        const resp = await fetch('/admin/security/mfa/disable', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code })
        });

        if (resp.ok) {
            alert("MFA desactivado correctamente");
            location.reload();
        } else {
            const data = await resp.json();
            alert("Error: " + (data.detail || "Código incorrecto"));
        }
    } catch (e) {
        alert("Error de conexión");
    }
}

function cancelSetup() {
    document.getElementById('mfa-actions').style.display = 'block';
    document.getElementById('setup-area').style.display = 'none';
    document.getElementById('disable-area').style.display = 'none';
}

// Inicializar
document.addEventListener('DOMContentLoaded', checkMfaStatus);
