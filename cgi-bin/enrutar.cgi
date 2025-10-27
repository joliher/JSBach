#!/bin/bash
echo "Content-type: text/html; charset=utf-8"
echo ""

/bin/cat << EOM
<html>
<head>
  <meta charset="utf-8">
  <title>Hola món CGI</title>
</head>
<body>
<pre>
EOM

comand=$(echo "$QUERY_STRING" | sed -n 's/^.*comand=\([^&]*\).*$/\1/p')

echo "Configuració ENRUTAMENT <br>"

{
	echo "nat $comand"
	echo "exit" 
} | nc 127.0.0.1 1234 | sed 's/CLI>//g'

/bin/cat << EOM
</pre>
</body>
</html>
EOM

