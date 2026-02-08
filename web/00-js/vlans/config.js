let vlanCache = {};

function isValidCIDR(ip) {
    const parts = ip.split('/');
    if (parts.length !== 2) return false;
    const ipAddr = parts[0];
    const mask = parseInt(parts[1]);
    if (isNaN(mask) || mask < 1 || mask > 32) return false;
    const ipParts = ipAddr.split('.');
    if (ipParts.length !== 4) return false;
    for (let part of ipParts) {
        const num = parseInt(part);
        if (isNaN(num) || num < 0 || num > 255) return false;
    }
    return true;
}


function isValidNetworkIP(ip) {
    if (!isValidCIDR(ip)) return false;
    const info = getNetworkInfo(ip);
    if (!info) return false;
    return info.ipNum === info.networkNum;
}


function getNetworkInfo(ipCidr) {
    try {
        const [ip, maskStr] = ipCidr.split('/');
        const mask = parseInt(maskStr);
        const ipParts = ip.split('.').map(Number);
        const ipNum = (ipParts[0] << 24) | (ipParts[1] << 16) | (ipParts[2] << 8) | ipParts[3];
        const maskNum = (0xFFFFFFFF << (32 - mask)) >>> 0;

        const networkNum = (ipNum & maskNum) >>> 0;
        const broadcastNum = (networkNum | (~maskNum & 0xFFFFFFFF)) >>> 0;

        return { ipNum: ipNum >>> 0, networkNum, broadcastNum };
    } catch (e) {
        return null;
    }
}

function isValidInterfaceIP(ip) {
    if (!isValidCIDR(ip)) return false;
    const info = getNetworkInfo(ip);
    if (!info) return false;
    return info.ipNum !== info.networkNum && info.ipNum !== info.broadcastNum;
}

function isIpInNetwork(ipInterface, ipNetwork) {
    try {
        const ipParts = ipInterface.split('/')[0].split('.').map(p => parseInt(p));
        const netParts = ipNetwork.split('/')[0].split('.').map(p => parseInt(p));
        const mask = parseInt(ipNetwork.split('/')[1]);

        // Convertir IP e IP de red a números de 32 bits
        const ipNum = (ipParts[0] << 24) | (ipParts[1] << 16) | (ipParts[2] << 8) | ipParts[3];
        const netNum = (netParts[0] << 24) | (netParts[1] << 16) | (netParts[2] << 8) | netParts[3];

        // Crear máscara de red
        const maskNum = (0xFFFFFFFF << (32 - mask)) >>> 0;

        // Verificar si la IP está en la red
        return (ipNum & maskNum) === (netNum & maskNum);
    } catch (e) {
        return false;
    }
}

function haveSameMask(ipInterface, ipNetwork) {
    try {
        const mask1 = parseInt(ipInterface.split('/')[1]);
        const mask2 = parseInt(ipNetwork.split('/')[1]);
        return mask1 === mask2;
    } catch (e) {
        return false;
    }
}

function validateVlanFields(name, ipInterface, ipNetwork) {
    if (!name) {
        return "Nombre no puede estar vacio";
    }

    if (!ipInterface) {
        return "IP de interfaz no puede estar vacia";
    }

    if (!isValidCIDR(ipInterface)) {
        return "Formato de IP de interfaz invalido. Esperado: 192.168.1.1/24 (incluir mascara CIDR)";
    }

    if (!isValidInterfaceIP(ipInterface)) {
        return "IP de interfaz no puede terminar en 0 (direccion de red) ni en 255 (broadcast). Use una IP de host valida (ej: 192.168.1.1).";
    }

    if (!ipNetwork) {
        return "IP de red no puede estar vacia";
    }

    if (!isValidNetworkIP(ipNetwork)) {
        return "IP de red debe terminar en 0 (ej: 192.168.1.0/24). Formato esperado: X.X.X.0/mascara";
    }

    if (!haveSameMask(ipInterface, ipNetwork)) {
        const maskIface = ipInterface.split('/')[1];
        const maskNet = ipNetwork.split('/')[1];
        return `Las mascaras no coinciden. IP interfaz: /${maskIface}, IP red: /${maskNet}. Deben ser iguales.`;
    }

    if (!isIpInNetwork(ipInterface, ipNetwork)) {
        const ipAddr = ipInterface.split('/')[0];
        return `La IP de interfaz ${ipAddr} no pertenece a la red ${ipNetwork}. Rango valido: desde ${ipNetwork.split('/')[0].replace(/0$/, '1')} hasta ${ipNetwork.split('/')[0].replace(/0$/, '254')}`;
    }

    return null;
}

async function loadVlans() {
    try {
        const response = await fetch("/admin/vlans", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({
                action: "config",
                params: { action: "show", format: "json" }
            })
        });

        const data = await response.json();

        if (!response.ok) {
            document.getElementById("output").textContent = data.detail || "Error cargando VLANs";
            return;
        }

        // Parsear VLANs del mensaje (ahora es JSON)
        let vlans = [];
        try {
            if (typeof data.message === 'string' && (data.message.startsWith('[') || data.message.startsWith('{'))) {
                vlans = JSON.parse(data.message);
                if (!Array.isArray(vlans)) vlans = [];
            } else {
                // Fallback si devuelve string antiguo (por si acaso) o mensaje "No hay VLANs"
                if (data.message.includes("No hay VLANs")) {
                    vlans = [];
                } else {
                    // Intento de fallback regex (opcional, o mostrar error)
                    console.warn("Recibido formato no JSON:", data.message);
                }
            }
        } catch (e) {
            console.error("Error parseando VLANs:", e);
            document.getElementById("output").textContent = "Error procesando datos del servidor";
            return;
        }

        const tbody = document.querySelector("#vlansTable tbody");
        tbody.innerHTML = "";
        vlanCache = {};

        // Ordenar por ID
        vlans.sort((a, b) => a.id - b.id);

        vlans.forEach(vlan => {
            vlanCache[vlan.id] = vlan;

            const tr = document.createElement("tr");
            tr.dataset.id = vlan.id;

            const isProtected = (vlan.id === 1 || vlan.id === 2);

            tr.innerHTML = `
    <td>${vlan.id}</td>
    <td>${vlan.name || ""}</td>
    <td>${vlan.ip_interface || ""}</td>
    <td>${vlan.ip_network || ""}</td>
    <td>
    <button class="btn-edit" onclick="editRow(${vlan.id})">Modificar</button>
    <button class="btn-delete" onclick="deleteVlan(${vlan.id})" ${isProtected ? 'disabled' : ''}>Eliminar</button>
    </td>
    `;

            tbody.appendChild(tr);
        });

        const outputDiv = document.getElementById("output");
        if (outputDiv) outputDiv.textContent = "";

    } catch (err) {
        const outputDiv = document.getElementById("output");
        if (outputDiv) outputDiv.textContent = "Error: " + err.message;
    }
}

function editRow(id) {
    const tr = document.querySelector(`tr[data-id="${id}"]`);
    const vlan = vlanCache[id];

    tr.innerHTML = `
    <td>${vlan.id}</td>
    <td><input type="text" value="${vlan.name || ""}"></td>
    <td><input type="text" value="${vlan.ip_interface || ""}"></td>
    <td><input type="text" value="${vlan.ip_network || ""}"></td>
    <td>
    <button class="btn-save" onclick="saveRow(${id})">Guardar</button>
    <button class="btn-cancel" onclick="cancelEdit()">Cancelar</button>
    </td>
    `;
}

async function saveRow(id) {
    const tr = document.querySelector(`tr[data-id="${id}"]`);
    const inputs = tr.querySelectorAll("input");
    const [name, ip_interface, ip_network] = Array.from(inputs).map(i => i.value.trim());
    const output = document.getElementById("output");

    const validationError = validateVlanFields(name, ip_interface, ip_network);
    if (validationError) {
        output.textContent = `❌ Error: ${validationError}`;
        return;
    }

    try {
        const response = await fetch("/admin/vlans", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({
                action: "config",
                params: {
                    action: "add",
                    id: id,
                    name: name,
                    ip_interface: ip_interface,
                    ip_network: ip_network
                }
            })
        });

        const data = await response.json();

        if (!response.ok) {
            output.textContent = "❌ " + (data.detail || data.message || "Error desconocido");
            return;
        }

        output.textContent = `✅ VLAN ${id} actualizada`;
        loadVlans();

    } catch (err) {
        document.getElementById("output").textContent = "Error: " + err.message;
    }
}

function cancelEdit() {
    loadVlans();
}

async function deleteVlan(id) {
    if (!confirm(`¿Eliminar VLAN ${id}?`)) return;

    try {
        const response = await fetch("/admin/vlans", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({
                action: "config",
                params: {
                    action: "remove",
                    id: id
                }
            })
        });

        const data = await response.json();
        document.getElementById("output").textContent = data.message || data.detail;
        loadVlans();

    } catch (err) {
        document.getElementById("output").textContent = "Error: " + err.message;
    }
}

/* -----------------------------
Inicialización cuando el DOM está listo
----------------------------- */

document.addEventListener("DOMContentLoaded", function () {
    const vlanForm = document.getElementById("vlanForm");

    vlanForm.addEventListener("submit", async (e) => {
        e.preventDefault();

        const form = e.target;
        const vlanId = form.id.value.trim();
        const name = form.name.value.trim();
        const ip_interface = form.ip_interface.value.trim();
        const ip_network = form.ip_network.value.trim();
        const output = document.getElementById("output");

        // Validar ID
        if (!vlanId) {
            output.textContent = "❌ Error: ID de VLAN no puede estar vacío";
            return;
        }

        const vlanIdNum = parseInt(vlanId);
        const existing = Boolean(vlanCache[vlanIdNum]);
        if (isNaN(vlanIdNum) || vlanIdNum < 1 || vlanIdNum > 4094) {
            output.textContent = "❌ Error: ID de VLAN debe estar entre 1 y 4094";
            return;
        }

        if (vlanIdNum === 1 || vlanIdNum === 2) {
            output.textContent = "❌ Error: VLANs 1 y 2 están protegidas y preconfiguradas";
            return;
        }

        const validationError = validateVlanFields(name, ip_interface, ip_network);
        if (validationError) {
            output.textContent = `❌ Error: ${validationError}`;
            return;
        }

        try {
            const response = await fetch("/admin/vlans", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
                body: JSON.stringify({
                    action: "config",
                    params: {
                        action: "add",
                        id: parseInt(form.id.value),
                        name: form.name.value,
                        ip_interface: ip_interface,
                        ip_network: ip_network
                    }
                })
            });

            const data = await response.json();

            if (!response.ok) {
                output.textContent = "❌ " + (data.detail || data.message || "Error desconocido");
            } else if (existing) {
                output.textContent = `✅ VLAN ${vlanIdNum} actualizada`;
            } else {
                output.textContent = `✅ VLAN ${vlanIdNum} agregada`;
            }

            form.reset();
            loadVlans();

        } catch (err) {
            document.getElementById("output").textContent = "❌ Error: " + err.message;
        }
    });

    // Cargar VLANs iniciales
    loadVlans();
});