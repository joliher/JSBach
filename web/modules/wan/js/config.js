/* /web/modules/wan/js/config.js */

let userEditing = false;

function isValidIPv4(ip) {
    const regex = /^(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)){3}$/;
    return regex.test(ip);
}

async function loadWanConfiguration() {
    try {
        const response = await fetch("/admin/config/wan/wan.json", { credentials: "include" });
        if (response.ok) {
            const wanConfig = await response.json();
            const wanInterface = wanConfig.interface || "No configurada";
            const wanMode = wanConfig.mode || "No definido";
            const wanStatus = wanConfig.status === 1 ? "Activo" : "Inactivo";

            document.getElementById("wan-details").textContent = `${wanInterface} (Modo: ${wanMode}, Estado: ${wanStatus})`;
            document.getElementById("wan-info-container").style.display = "block";
            document.getElementById("dhcp-notice").style.display = (wanMode === "dhcp") ? "block" : "none";

            if (!userEditing) {
                document.getElementById("interface").value = wanConfig.interface || "";
                document.getElementById("mode").value = wanConfig.mode || "dhcp";
                document.getElementById("manual-fields").classList.toggle("hidden", wanConfig.mode !== "manual");
                if (wanConfig.mode === "manual") {
                    document.getElementById("ip").value = wanConfig.ip || "";
                    document.getElementById("mask").value = wanConfig.mask || "";
                    document.getElementById("gateway").value = wanConfig.gateway || "";
                    document.getElementById("dns").value = wanConfig.dns || "";
                }
            }
        }
    } catch (err) { console.info("No wan config found."); }
}

async function handleFormSubmit(e) {
    e.preventDefault();
    const resultDiv = document.getElementById("config-result");
    resultDiv.textContent = "⏳ Guardando...";
    resultDiv.style.color = "var(--text-secondary)";

    const params = {
        interface: document.getElementById("interface").value.trim(),
        mode: document.getElementById("mode").value
    };

    if (params.mode === "manual") {
        params.ip = document.getElementById("ip").value.trim();
        params.mask = document.getElementById("mask").value.trim();
        params.gateway = document.getElementById("gateway").value.trim();
        params.dns = document.getElementById("dns").value.trim();

        if (!isValidIPv4(params.ip) || !isValidIPv4(params.gateway)) {
            resultDiv.textContent = "❌ IP o Gateway inválido";
            resultDiv.style.color = "var(--error)";
            return;
        }
    }

    try {
        const response = await fetch("/admin/wan", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ action: "config", params })
        });
        const data = await response.json();
        if (response.ok) {
            resultDiv.textContent = "✅ " + data.message;
            resultDiv.style.color = "var(--success)";
            loadWanConfiguration();
            userEditing = false;
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
    loadWanConfiguration();

    const modeSelect = document.getElementById("mode");
    modeSelect?.addEventListener("change", () => {
        document.getElementById("manual-fields").classList.toggle("hidden", modeSelect.value !== "manual");
        document.getElementById("dhcp-notice").style.display = (modeSelect.value === "dhcp") ? "block" : "none";
        userEditing = true;
    });

    ['interface', 'ip', 'mask', 'gateway', 'dns'].forEach(id => {
        document.getElementById(id)?.addEventListener('input', () => { userEditing = true; });
    });

    document.getElementById('wan-form')?.addEventListener('submit', handleFormSubmit);
});
