/* /web/modules/tagging/js/config.js */

function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

let taggingCache = {};

async function loadTagging() {
    const tbody = document.querySelector("#taggingTable tbody");
    if (!tbody) return;

    try {
        const response = await fetch("/admin/config/tagging/tagging.json", { credentials: "include" });
        if (response.ok) {
            const config = await response.json();
            const interfaces = config.interfaces || [];
            tbody.innerHTML = "";
            taggingCache = {};

            if (!Array.isArray(interfaces) || interfaces.length === 0) {
                tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;">No hay interfaces configuradas.</td></tr>';
                return;
            }

            interfaces.forEach(cfg => {
                const name = cfg.name || "N/A";
                taggingCache[name] = cfg;
                const tr = document.createElement("tr");
                tr.dataset.name = name;
                renderTaggingRow(tr, cfg);
                tbody.appendChild(tr);
            });
        }
    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="3" style="color:var(--error); text-align:center;">Error al cargar interfaces.</td></tr>';
    }
}

function renderTaggingRow(tr, cfg) {
    const name = cfg.name || "N/A";
    let detail = "";
    if (cfg.vlan_untag) detail += `<span class="badge" style="background:rgba(59, 130, 246, 0.1); color:#3b82f6;">UNTAG: ${cfg.vlan_untag}</span> `;
    if (cfg.vlan_tag) detail += `<span class="badge" style="background:rgba(225, 29, 72, 0.1); color:var(--accent-color);">TAG: ${cfg.vlan_tag}</span>`;

    tr.innerHTML = `
        <td><code>${escapeHtml(name)}</code></td>
        <td>${detail}</td>
        <td>
            <div class="action-group">
                <button class="btn btn-blue btn-small" onclick="editRow('${escapeHtml(name)}')" title="Editar">✏️</button>
                <button class="btn btn-red btn-small" onclick="deleteIface('${escapeHtml(name)}')" title="Eliminar">🗑️</button>
            </div>
        </td>
    `;
}

function editRow(name) {
    const cfg = taggingCache[name];
    if (!cfg) return;
    const tr = document.querySelector(`tr[data-name="${name}"]`);
    if (!tr) return;

    tr.classList.add('edit-mode-row');
    tr.innerHTML = `
        <td><code>${escapeHtml(name)}</code></td>
        <td>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                <div class="table-form-group">
                    <label>Untag</label>
                    <input type="text" class="inline-input" id="edit-untag-${name}" value="${escapeHtml(cfg.vlan_untag || '')}" placeholder="Ej: 10">
                </div>
                <div class="table-form-group">
                    <label>Tag</label>
                    <input type="text" class="inline-input" id="edit-tag-${name}" value="${escapeHtml(cfg.vlan_tag || '')}" placeholder="Ej: 10,20">
                </div>
            </div>
        </td>
        <td>
            <div class="action-group">
                <button class="btn btn-green btn-small" onclick="saveInline('${escapeHtml(name)}')" title="Guardar">💾</button>
                <button class="btn btn-red btn-small" onclick="cancelEdit('${escapeHtml(name)}')" title="Cancelar">❌</button>
            </div>
        </td>
    `;
}

function cancelEdit(name) {
    const tr = document.querySelector(`tr[data-name="${name}"]`);
    const cfg = taggingCache[name];
    if (tr && cfg) {
        tr.classList.remove('edit-mode-row');
        renderTaggingRow(tr, cfg);
    }
}

async function saveInline(name) {
    const untag = document.getElementById(`edit-untag-${name}`).value.trim();
    const tag = document.getElementById(`edit-tag-${name}`).value.trim();

    const resultDiv = document.getElementById("config-result");
    resultDiv.textContent = "⏳ Guardando...";
    resultDiv.style.color = "var(--text-secondary)";

    const params = { action: "add", name, vlan_untag: untag, vlan_tag: tag };

    try {
        const response = await fetch("/admin/tagging", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ action: "config", params })
        });
        const data = await response.json();
        if (data.success) {
            resultDiv.textContent = "✅ " + data.message;
            resultDiv.style.color = "var(--success)";
            loadTagging();
        } else {
            showToast("❌ Error: " + (data.message || data.detail || "Error desconocido")); resultDiv.textContent = "";
            resultDiv.style.color = "var(--error)";
        }
    } catch (err) {
        resultDiv.textContent = "❌ Error de conexión";
        resultDiv.style.color = "var(--error)";
    }
}

async function deleteIface(name) {
    if (!confirm(`¿Eliminar configuración de la interfaz ${name}?`)) return;
    const resultDiv = document.getElementById("config-result");
    resultDiv.textContent = "⏳ Eliminando...";

    try {
        const response = await fetch("/admin/tagging", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ action: "config", params: { action: "remove", name } })
        });
        const data = await response.json();
        if (data.success) {
            resultDiv.textContent = "✅ " + data.message;
            resultDiv.style.color = "var(--success)";
            loadTagging();
        } else {
            showToast("❌ Error: " + (data.message || data.detail || "Error desconocido")); resultDiv.textContent = "";
            resultDiv.style.color = "var(--error)";
        }
    } catch (err) {
        resultDiv.textContent = "❌ Error de conexión";
        resultDiv.style.color = "var(--error)";
    }
}

async function handleTaggingSubmit(e) {
    e.preventDefault();
    const resultDiv = document.getElementById("config-result");
    resultDiv.textContent = "⏳ Guardando...";
    resultDiv.style.color = "var(--text-secondary)";

    const params = {
        action: "add",
        name: document.getElementById("iface-name").value.trim(),
        vlan_untag: document.getElementById("iface-untag").value.trim(),
        vlan_tag: document.getElementById("iface-tag").value.trim()
    };

    try {
        const response = await fetch("/admin/tagging", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ action: "config", params })
        });
        const data = await response.json();
        if (data.success) {
            resultDiv.textContent = "✅ " + data.message;
            resultDiv.style.color = "var(--success)";
            document.getElementById("tagging-form").reset();
            loadTagging();
            // Scroll back to table to see changes
            window.scrollTo({ top: 0, behavior: 'smooth' });
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
    loadTagging();
    document.getElementById("tagging-form")?.addEventListener("submit", handleTaggingSubmit);
});
