#!/bin/bash

if [ $(whoami) != "root" ]; then
	echo "Debe de ejecutarse como root."
	exit 1
fi

# NetworkManager
echo "Deshabilitando NetworkManager..."
systemctl stop NetworkManager && systemctl disable NetworkManager &>/dev/null

