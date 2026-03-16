/* /web/modules/expect/js/config.js */

let switchesCache = {};
let profileData = null;
let globalParams = {};
let interfaceParams = {};
let interfaceBlockId = 0;

// --- UTILS ---
function parseSwitchesMessage(message) {
    if (!message) return { switches: [] };
    if (typeof message === 'object') return message;
    if (typeof message === 'string') {
        const trimmed = message.trim();
        if (!trimmed) return { switches: [] };
        if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
            try {
                const parsed = JSON.parse(trimmed);
                return Array.isArray(parsed) ? { switches: parsed } : parsed;
            } catch (e) { return { switches: [] }; }
        }
    }
    return { switches: [] };
}

// --- LOAD DATA ---
async function loadSwitchesForConfig() {
    const targetIpSelect = document.getElementById('target-ip');
    if (!targetIpSelect) return;
    try {
        const response = await fetch('/admin/expect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'list_switches' }),
            credentials: 'include'
        });
        const result = await response.json();
        const data = parseSwitchesMessage(result.message);
        const switches = data.switches || [];
        switchesCache = {};
        switches.forEach(sw => { if (sw && sw.ip) switchesCache[sw.ip] = sw; });

        const savedIp = sessionStorage.getItem('expectSelectedIp');
        targetIpSelect.innerHTML = '<option value="" disabled selected>Seleccione un switch</option>';
        switches.forEach(sw => {
            const option = document.createElement('option');
            option.value = sw.ip;
            option.textContent = sw.name ? `${sw.name} (${sw.ip})` : sw.ip;
            if (savedIp === sw.ip) option.selected = true;
            targetIpSelect.appendChild(option);
        });

        if (!savedIp && switches[0]) targetIpSelect.value = switches[0].ip;
        updateAuthFeedback(targetIpSelect.value);
        await loadProfileParams();
    } catch (e) { console.error(e); }
}

async function loadProfileParams() {
    const ip = document.getElementById('target-ip')?.value;
    const profileId = switchesCache[ip]?.profile;
    if (!profileId) return;
    try {
        const response = await fetch(`/admin/expect/profiles/${profileId}`, { credentials: 'include' });
        profileData = await response.json();
        globalParams = {}; interfaceParams = {};
        for (let [key, val] of Object.entries(profileData.parameters)) {
            // Si no hay context, por defecto es interface (o podríamos intentar inferir)
            if (val.context === 'global' || key === 'hostname') globalParams[key] = val;
            else interfaceParams[key] = val;
        }
        document.getElementById('global-config-container').innerHTML = '';
        document.getElementById('global-config-container').style.display = 'none';
        document.getElementById('interface-config-container').innerHTML = '';
        // auth_required se asume true o se maneja desde el switch si se prefiere
        toggleAuthWarning();
    } catch (e) { console.error(e); }
}

function updateAuthFeedback(ip) {
    const sw = switchesCache[ip];
    document.getElementById('auth-feedback-user').textContent = sw?.user || '-';
    document.getElementById('auth-feedback-profile').textContent = sw?.profile || '-';
    document.getElementById('auth-feedback').classList.remove('hidden');
}

function toggleAuthWarning() {
    const show = document.getElementById('auth_required').checked;
    document.getElementById('auth-warning-box').classList.toggle('hidden', !show);
}

// --- DYNAMIC ROWS ---
function addParamRow(context, key, blockId = null) {
    const params = context === 'global' ? globalParams : interfaceParams;
    let mainContainer = context === 'global' ? document.getElementById('global-config-container') : document.getElementById(blockId).querySelector('.interface-params-list');

    const wrapper = document.createElement('div');
    wrapper.style.marginBottom = '10px';
    const row = document.createElement('div');
    row.className = 'config-row';

    const paramDef = params[key];
    let inputHtml = `<input type="text" placeholder="Valor para ${key}" required>`;
    if (paramDef?.validation?.startsWith('enum:')) {
        const options = paramDef.validation.replace('enum:', '').split(',');
        inputHtml = `<select required>${options.map(o => `<option value="${o}">${o}</option>`).join('')}</select>`;
    }

    row.innerHTML = `<div class="param-label" data-key="${key}">${key.toUpperCase()}</div>${inputHtml}<button type="button" class="btn btn-red btn-small" onclick="this.closest('.config-row').parentElement.remove()">🗑️</button>`;
    wrapper.appendChild(row);
    mainContainer.appendChild(wrapper);
    if (context === 'global') mainContainer.style.display = 'block';

    // Auto-close menu
    document.querySelectorAll('.param-menu').forEach(m => m.style.display = 'none');
}

function showParamMenu(btn, context, blockId = null) {
    const menu = context === 'global' ? document.getElementById('global-menu') : btn.nextElementSibling;
    const params = context === 'global' ? globalParams : interfaceParams;
    if (Object.keys(params).length === 0) {
        alert("El perfil no tiene parámetros disponibles para este contexto.");
        return;
    }
    let html = `<div class="menu-header">Añadir Parámetro</div>`;
    Object.keys(params).forEach(k => {
        html += `<button type="button" onclick="addParamRow('${context}', '${k}', ${blockId ? `'${blockId}'` : 'null'})">${k.toUpperCase()}</button>`;
    });
    menu.innerHTML = html;
    menu.style.display = 'block';
}

function addInterfaceBlock() {
    const container = document.getElementById('interface-config-container');
    const bId = `interface-block-${interfaceBlockId++}`;
    const div = document.createElement('div');
    div.className = 'config-block';
    div.id = bId;
    div.innerHTML = `
        <div class="config-row">
            <div class="param-label" style="background: rgba(255,255,255,0.05); padding: 5px; border-radius: 4px;">PUERTOS</div>
            <input type="text" class="port-input" placeholder="Ej: 1-4, 10, 20-25" required>
            <button type="button" class="btn btn-red btn-small" onclick="this.closest('.config-block').remove()">🗑️</button>
        </div>
        <div class="interface-params-list" style="margin-left: 20px; border-left: 2px solid rgba(255,255,255,0.1); padding-left: 15px;"></div>
        <div class="add-param-container" style="margin-top: 15px; position: relative;">
            <button type="button" class="btn btn-blue btn-small" onclick="showParamMenu(this, 'interface', '${bId}')">➕ Añadir Parámetro</button>
            <div class="param-menu"></div>
        </div>
    `;
    container.appendChild(div);
}

// --- EXECUTION ---
function serializeConfig() {
    const actions = [];
    const globalBlock = { context: 'global', parameters: {} };
    document.querySelectorAll('#global-config-container .config-row').forEach(row => {
        const key = row.querySelector('.param-label').dataset.key;
        const input = row.querySelector('input, select');
        if (key && input) globalBlock.parameters[key] = input.value;
    });
    if (Object.keys(globalBlock.parameters).length > 0) actions.push(globalBlock);

    document.querySelectorAll('#interface-config-container .config-block').forEach(block => {
        const portInput = block.querySelector('.port-input');
        if (!portInput) return;
        const ifaceBlock = { context: 'interface', ports: portInput.value, parameters: {} };
        block.querySelectorAll('.interface-params-list .config-row').forEach(row => {
            const key = row.querySelector('.param-label').dataset.key;
            const input = row.querySelector('input, select');
            if (key && input) ifaceBlock.parameters[key] = input.value;
        });
        actions.push(ifaceBlock);
    });
    return actions;
}

async function handleOrchestration(e) {
    e.preventDefault();
    const ip = document.getElementById('target-ip').value;
    const auth_required = document.getElementById('auth_required').checked;
    const dry_run = document.getElementById('dry_run').checked;
    const actions = serializeConfig();

    if (!ip) { alert("Seleccione un switch"); return; }
    if (actions.length === 0) { alert("Añada al menos una configuración (Global o Interfaz)"); return; }

    const output = document.getElementById('output');
    output.textContent = "⏳ Ejecutando orquestación... Esto puede tardar unos segundos.";
    output.className = "output";
    output.classList.remove('hidden');

    try {
        const response = await fetch('/admin/expect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                action: 'run',
                params: { ip, auth_required, dry_run, actions }
            }),
            credentials: 'include'
        });
        const result = await response.json();
        output.textContent = result.message || (result.success ? "Ejecución finalizada con éxito." : "Error en la ejecución.");
        output.style.color = result.success ? 'var(--success)' : 'var(--error)';
    } catch (e) {
        output.textContent = "Error de red al conectar con el servidor.";
        output.style.color = 'var(--error)';
    }
}

// --- INITIALIZATION ---
window.addEventListener('DOMContentLoaded', () => {
    loadSwitchesForConfig();

    document.getElementById('target-ip')?.addEventListener('change', (e) => {
        sessionStorage.setItem('expectSelectedIp', e.target.value);
        updateAuthFeedback(e.target.value);
        loadProfileParams();
    });

    document.getElementById('auth_required')?.addEventListener('change', toggleAuthWarning);
    document.getElementById('expect-form')?.addEventListener('submit', handleOrchestration);

    // Close menus on click outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.add-param-container')) {
            document.querySelectorAll('.param-menu').forEach(m => m.style.display = 'none');
        }
    });
});
