/* /web/modules/nat/js/config.js */

async function loadConfigurations() {
    // Load WAN config
    try {
        const response = await fetch("/admin/config/wan/wan.json", { credentials: "include" });
        if (response.ok) {
            const data = await response.json();
            if (data.interface) {
                document.getElementById("wan-details").textContent = `${data.interface} (Modo: ${data.mode})`;
                document.getElementById("wan-info-container").style.display = "block";
            }
        }
    } catch (err) { }

    // Load NAT config
    try {
        const response = await fetch("/admin/config/nat/nat.json", { credentials: "include" });
        if (response.ok) {
            const data = await response.json();
            if (data.interface) {
                document.getElementById("nat-details").textContent = data.interface;
                document.getElementById("nat-info-container").style.display = "block";
                document.getElementById("interface").value = data.interface;
            }
        }
    } catch (err) { }
}

async function handleNatSubmit(e) {
    e.preventDefault();
    const resultDiv = document.getElementById("config-result");
    resultDiv.textContent = "⏳ Guardando...";
    resultDiv.style.color = "var(--text-secondary)";

    const interface = document.getElementById("interface").value.trim();

    try {
        const response = await fetch("/admin/nat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ action: "config", params: { interface } })
        });
        const data = await response.json();
        if (data.success) {
            resultDiv.textContent = "✅ " + data.message;
            resultDiv.style.color = "var(--success)";
            loadConfigurations();
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
    loadConfigurations();
    document.getElementById("nat-form")?.addEventListener("submit", handleNatSubmit);
});
