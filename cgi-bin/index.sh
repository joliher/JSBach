#!/bin/bash

/bin/cat << EOF
Content-type: text/html

<html>
<head>
	<title>NIGGA</title>
</head>
<body>
	<h2>Hola Mundo</h2>
</body>
</html>
EOF

echo "?" | nc -N 127.0.0.1 1234
