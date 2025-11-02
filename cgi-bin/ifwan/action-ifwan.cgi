#!/bin/bash
echo "Content-type: text/html; charset=utf-8"
echo ""

/bin/cat << EOM
<html>
  <head>
    <meta charset="utf-8">
    <title>Hola món CGI</title>
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
    <h3>Configuración WAN</h3>
    <pre>
EOM

QUERY_STRING_DECODED=$(echo "$QUERY_STRING" | sed 's/+/ /g; s/%/\\x/g' | xargs -0 printf "%b")

param=$(echo "$QUERY_STRING_DECODED" | sed -n 's/.*param=\([^&]*\).*/\1/p')
mode=$(echo "$QUERY_STRING_DECODED" | sed -n 's/.*mode=\([^&]*\).*/\1/p')
interfaz=$(echo "$QUERY_STRING_DECODED" | sed -n 's/.*interface=\([^&]*\).*/\1/p')
ipmask=$(echo "$QUERY_STRING_DECODED" | sed -n 's/.*ipmask=\([^&]*\).*/\1/p')
gtw=$(echo "$QUERY_STRING_DECODED" | sed -n 's/.*gtw=\([^&]*\).*/\1/p')
dns=$(echo "$QUERY_STRING_DECODED" | sed -n 's/.*dns=\([^&]*\).*/\1/p')

if [ $param == "--config" ]; then
	{
		echo "ifwan $param $mode $interfaz $ipmask $gtw $dns"
		echo "exit"
	} | nc 127.0.0.1 1234 | sed 's/CLI>//g'
else
	{
		echo "ifwan $param"
		echo "exit"
	} | nc 127.0.0.1 1234 | sed 's/CLI>//g'

fi

/bin/cat << EOM
    </pre>
  </body>
</html>
EOM

