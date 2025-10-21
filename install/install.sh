#!/bin/bash

if [ $(whoami) != "root" ]; then
	echo "Debe de ejecutarse como root."
	exit 1
fi


# Paquetes adicionales
apt install curl net-tools apache2

a2enmod cgi

# NetworkManager
echo "Deshabilitando NetworkManager..."
systemctl stop NetworkManager && systemctl disable NetworkManager &>/dev/null


