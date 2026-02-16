/* /web/js/login.js */

async function login() {
    const user = document.getElementById('username').value;
    const pass = document.getElementById('password').value;
    const errorDiv = document.getElementById('error');

    if (!user || !pass) {
        errorDiv.textContent = "Ingrese usuario y contraseña";
        return;
    }

    errorDiv.textContent = "⌛ Autenticando...";
    errorDiv.style.color = "#3b82f6";

    try {
        const response = await fetch('/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: user, password: pass })
        });

        const result = await response.json();

        if (response.ok) {
            window.location.href = "/";
        } else {
            errorDiv.textContent = result.detail || "Error de autenticación";
            errorDiv.style.color = "#ef4444";
        }
    } catch (e) {
        errorDiv.textContent = "Error de conexión con el servidor";
        errorDiv.style.color = "#ef4444";
    }
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') login();
});
