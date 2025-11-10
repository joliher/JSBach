#!/bin/bash

if [ $(whoami) != "root" ]; then
	echo "Debes de ser root"
	exit 1
fi

source /usr/local/JSBach/config/variables.conf
trap "echo 'Saliendo...'; exit 0" SIGINT SIGTERM

while true; do
	socat TCP-LISTEN:1234,reuseaddr,bind=127.0.0.1 EXEC:"$DIR/$PROYECTO/$DIR_SCRIPTS/cli"
	echo "Cliente desconectado, reiniciando escucha"
	sleep 1
done
