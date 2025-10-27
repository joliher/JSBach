#!/bin/bash

if [ $(whoami) != "root" ]; then
	echo "Debes de ser root"
	exit 1
fi

while true; do
	socat TCP-LISTEN:1234,reuseaddr,bind=127.0.0.1 EXEC:/usr/local/JSBach/scripts/cli
	echo "Cliente desconectado, reiniciando escucha"
	sleep 1
done
