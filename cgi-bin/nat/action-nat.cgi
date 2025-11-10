#!/bin/bash
echo "Content-type: text/html; charset=utf-8"
echo ""

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
    </style>
  </head>
  <body>
    <h3>Configuración ENRUTAMIENTO</h3>
    <pre>
EOM

param=$(echo "$QUERY_STRING" | sed -n 's/^.*param=\([^&]*\).*$/\1/p')
{
	echo "nat $param"
	echo "exit" 
} | nc 127.0.0.1 1234 | sed 's/CLI>//g'

/bin/cat << EOM
    </pre>
  </body>
</html>
EOM

