#!/bin/bash

source /usr/local/JSBach/conf/variables.txt

echo "Content-Type:text/html;charset=utf-8"

/bin/cat << EOM

<html>
  <head>
    <meta http-equiv=Content-Type content="text/html; charset=windows-1252">
    <meta content="MSHTML 6.00.2900.3660" name=GENERATOR>

    <style type="text/css">
<!--
      .estado {
        font-size: 18px;
        font-style: normal;
        color: #e9ab17;
        font-weight: bold;
        font-family: Georgia, "Times New Roman", Times, serif;
      }

      .cabecera {
        font-family: Verdana, Arial, Helvetica, sans-serif;
        color: #2A5B45;
      }

      th {
          text-align: left;
      }

      .Estilo1 {color: #FF00FF}
      .Estilo2 {color: #000000}
-->    
      /* Estilos generales para los botones */
      button {
        background-color: #f0f0f0;
        border: 1px solid #ccc;
        padding: 10px;
        cursor: pointer;
        margin: 5px;
      }

      /* Estilo para el botón activo (presionado) */
      button.active {
        background-color: #007bff;
        color: white;
        box-shadow: inset 0 4px 6px rgba(0, 0, 0, 0.1);
        border: 1px solid #0056b3;
        transform: translateY(2px);
      }
    </style>
  </head>
  <body link="#E9AB17" vlink="#E9AB17" alink="#E9AB17">

EOM

echo "<h1 align='center'>Administrando el Router <u>$HOSTNAME</u> con <u>$PROMPT</u></h1>"

/bin/cat << EOM

    <script>
      // Funciones para cambiar los frames
      function cambiarFrame(action) {
        var menuUrl, bodyUrl;
        
        // Establecer las URL correspondientes según la acción
        switch (action) {
          case 'wan':
            menuUrl = '/cgi-bin-JSBach/ifwan/menu-ifwan.cgi';
            bodyUrl = '/cgi-bin-JSBach/ifwan/action-ifwan.cgi';
            break;
          case 'nat':
            menuUrl = '/cgi-bin-JSBach/nat/menu-nat.cgi';
            bodyUrl = '/cgi-bin-JSBach/nat/action-nat.cgi';
            break;
          // Aquí puedes añadir más casos según los botones adicionales
        }

        window.top.frames['menu'].location.href = menuUrl;
        window.top.frames['body'].location.href = bodyUrl;
        
        // Llamamos a la función para actualizar el estado de los botones
        actualizarBoton(action);
      }

      // Función para actualizar la clase 'active' en los botones
      function actualizarBoton(accion) {
        var botones = document.querySelectorAll('button');
        botones.forEach(function(boton) {
          if (boton.getAttribute('data-action') === accion) {
            boton.classList.add('active');  // Marca el botón como activo
          } else {
            boton.classList.remove('active');  // Elimina la clase 'active' de otros botones
          }
        });
      }

      // Asegura que el botón correspondiente se marque al cargar la página
      window.onload = function() {
        var frameSrc = window.top.frames['body'].location.href;
        if (frameSrc.includes("ifwan")) {
          actualizarBoton('wan');
        } else if (frameSrc.includes("nat")) {
          actualizarBoton('nat');
        }
        // Aquí podrías añadir más condiciones para otros botones según sea necesario
      }
    </script>

    <table width="100%">
      <tr>
        <td>
          <!-- Botones del menú -->
          <button data-action="wan" onclick="cambiarFrame('wan')">WAN</button>
          <button data-action="nat" onclick="cambiarFrame('nat')">NAT</button>
          <!-- Aquí puedes agregar más botones de forma fácil y escalable -->
        </td>
      </tr>
    </table>

  </body>
</html>

EOM

