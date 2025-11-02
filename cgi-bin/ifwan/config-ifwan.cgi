#!/bin/bash

source /usr/local/JSBach/config/variables.conf

echo "Content-type: text/html; charset=utf-8"
echo ""

interfaces=$(ls /sys/class/net)
interfaces_filtradas=()

for iface in $interfaces; do
  if [[ "$iface" == "lo" ]]; then
    continue  
  fi
  if [[ -d "/sys/class/net/$iface/wireless" ]]; then
    continue  
  fi
  interfaces_filtradas+=("$iface")
done

/bin/cat << EOM
<html>
  <head>
    <meta charset="utf-8">
    <style>
      body {
        font-family: Arial, sans-serif;
        background-color: #eef3f8;
        color: #333;
        margin-bottom: 10px;
        padding: 10px;
      }

      .hidden-fields {
        display: none; /* Ocultos por defecto */
        margin-top: 10px;
      }
    </style>
    <script>
      function toggleManualFields() {
        var manualSelected = document.getElementById('manual').checked;
        var fields = document.getElementById('manualFields');
        fields.style.display = manualSelected ? 'block' : 'none';
      }
    </script>
  </head>
  <body>
    <h3>Configuración IFWAN</h3>

    <h4>Modo de la Interfaz WAN</h4>

    <form action="./action-ifwan.cgi" method="get">
      <input type="radio" id="dhcp" name="mode" value="dhcp" checked onclick="toggleManualFields()">
      <label for="dhcp">DHCP</label><br>

      <input type="radio" id="manual" name="mode" value="manual" onclick="toggleManualFields()">
      <label for="manual">Manual</label><br><br>

      <h4>Nombre de la Interfaz WAN</h4>
EOM

for iface in "${interfaces_filtradas[@]}"; do
  echo "<input type=\"radio\" id=\"$iface\" name=\"interface\" value=\"$iface\">"
  echo "<label for=\"$iface\">$iface</label><br>"
done
echo "<br>"

cat << EOM
      <div id="manualFields" class="hidden-fields">
        <h4>Dirección IP y máscara</h4>
        <input type="text" name="ipmask" placeholder="Ej: 192.168.0.100/24"><br><br>
        <br>
        <h4>Dirección de Gateway</h4>
        <input type="text" name="gtw" placeholder="Ej: 192.168.0.1"><br><br>
        <br>
        <h4>Dirección de Servidor DNS</h4>
        <input type="text" name="dns" placeholder="Ej: 1.1.1.1"><br><br>
        <br>
      </div>

      <button type="submit" name="param" value="--config">Aplicar configuración</button>
    </form>
  </body>
</html>
EOM
