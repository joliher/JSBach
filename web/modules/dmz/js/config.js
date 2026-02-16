/* /web/modules/dmz/js/config.js */

async function checkDependencies() {
    try {
        const response = await fetch("/admin/status", { credentials: "include" });
        const data = await response.json();
        if (data.firewall !== 'ACTIVO') {
            document.getElementById("firewall-warning").style.display = "block";
        }
    } catch (err) { }
}

async function handleDmzSubmit(e) {
    e.preventDefault();
    const resultDiv = document.getElementById("config-result");
    resultDiv.textContent = "⏳ Guardando...";
    resultDiv.style.color = "var(--text-secondary)";

    const params = {
        ip: document.getElementById("dest-ip").value.trim(),
        port: parseInt(document.getElementById("dest-port").value),
        protocol: document.getElementById("dest-protocol").value
    };

    try {
        const response = await fetch("/admin/dmz", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ action: "add_destination", params })
        });
        const data = await response.json();
        if (data.success) {
            resultDiv.textContent = "✅ " + data.message;
            resultDiv.style.color = "var(--success)";
            document.getElementById("dmz-form").reset();
        } else {
            showToast("❌ Error: " + (data.message || data.detail || "Error desconocido")); resultDiv.textContent = "";
            resultDiv.style.color = "var(--error)";
        }
    } catch (err) {
        resultDiv.textContent = "❌ Error de conexión";
        resultDiv.style.color = "var(--error)";
    }
}

window.addEventListener('DOMContentLoaded', () => {
    checkDependencies();
    document.getElementById("dmz-form")?.addEventListener("submit", handleDmzSubmit);
});
