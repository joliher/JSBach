#!/bin/bash

source /usr/local/JSBach/conf/variables.txt

echo "Content-Type:text/html;charset=utf-8"
/bin/cat << EOM

<html>
<head>
<title>Administrant el Router</title>
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
</style>
</head>
<body link="#E9AB17" vlink="#E9AB17" alink="#E9AB17">


EOM
echo "<h1 align="center">Administrant el Router "$HOSTNAME" amb "$PROMPT"</h1>"
/bin/cat << EOM

<script>
function wan(){
window.top.frames['menu'].location.href='/cgi-bin-JSBach/menu-ifwan.cgi';
window.top.frames['body'].location.href='/cgi-bin-JSBach/ifwan.cgi';
}
function enrutar(){
window.top.frames['menu'].location.href='/cgi-bin-JSBach/menu-enrutar.cgi';
window.top.frames['body'].location.href='/cgi-bin-JSBach/enrutar.cgi';
}
</script>

<table width="100%">
  <tr>
    <td>
      <!-- Botons esquerra -->
      <button onclick="wan()">WAN</button>
      <button onclick="enrutar()">ENRUTAR</button>    
  </tr>
</table>

</body>
</html>

EOM


