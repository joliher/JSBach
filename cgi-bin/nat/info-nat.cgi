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
EOM

comand=$(echo "$QUERY_STRING" | sed -n 's/^.*comand=\([^&]*\).*$/\1/p')

echo "<h3>Configuració ENRUTAMENT</h3><br>"
echo "<pre>"

{
	echo "nat $comand"
	echo "exit" 
} | nc 127.0.0.1 1234 | sed 's/CLI>//g'

/bin/cat << EOM
</pre>
</body>
</html>
EOM

