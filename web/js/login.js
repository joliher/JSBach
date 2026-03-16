/* /web/js/login.js */

let mfaRequired = false;

async function login() {
    const user = document.getElementById('username').value;
    const pass = document.getElementById('password').value;
    const mfaCode = document.getElementById('mfa_code').value;
    const errorDiv = document.getElementById('error');
    const mfaGroup = document.getElementById('mfa-group');
    const loginBtn = document.getElementById('login-btn');

    if (!user || !pass) {
        errorDiv.textContent = "Ingrese usuario y contraseña";
        return;
    }

    if (mfaRequired && !mfaCode) {
        errorDiv.textContent = "Ingrese el código de seguridad";
        return;
    }

    errorDiv.textContent = mfaRequired ? "⌛ Verificando código..." : "⌛ Autenticando...";
    errorDiv.style.color = "#3b82f6";

    try {
        const payload = { username: user, password: pass };
        if (mfaRequired) {
            payload.mfa_code = mfaCode;
        }

        const response = await fetch('/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const result = await response.json();

        if (response.ok) {
            if (result.mfa_required) {
                mfaRequired = true;
                mfaGroup.style.display = 'block';
                errorDiv.textContent = "Código requerido para " + user;
                errorDiv.style.color = "#fbbf24"; // Amarillo/Naranja para aviso
                document.getElementById('mfa_code').focus();
            } else {
                window.location.href = "/";
            }
        } else {
            errorDiv.textContent = result.detail || "Error de autenticación";
            errorDiv.style.color = "#ef4444";
            // Si el error es código inválido, mantener el estado MFA
            if (!result.mfa_required && !mfaRequired) {
                // Reset si falló el primer paso
            }
        }
    } catch (e) {
        errorDiv.textContent = "Error de conexión con el servidor";
        errorDiv.style.color = "#ef4444";
    }
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') login();
});
