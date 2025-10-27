#!/bin/bash

/bin/cat << EOM

<html>
<head>

EOM
echo '<title>Administracio de '$HOSTNAME'</title>'
/bin/cat << EOM

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
.Estilo1 {color: #FF00FF}
.Estilo2 {color: #000000}
-->
</style>
</head> 
<frameset rows="18%,82%" frameborder="1">
<frame src="/cgi-bin-JSBach/index-admin.cgi" name="menu-general" noresize="noresize">
<frameset cols="20%,80%">
<frame src="/cgi-bin-JSBach/<patata>.cgi" name="menu" noresize="noresize">
<frame src="/cgi-bin-JSBach/<patata>.cgi" name="body" noresize="noresize">
</frameset>
</frameset>
<noframes>
<body>Tu browser no soporta frames!</body>
</noframes>

</html>

EOM

