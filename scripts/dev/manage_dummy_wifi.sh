#!/bin/bash

# scripts/dev/manage_dummy_wifi.sh
# Gestiona una tarjeta Wi-Fi virtual para pruebas en JSBach

ACTION=$1
RADIOS=${2:-1}

setup() {
    echo "Cargando módulo mac80211_hwsim con $RADIOS radios..."
    sudo modprobe mac80211_hwsim radios=$RADIOS
    if [ $? -eq 0 ]; then
        echo "Interfaces creadas:"
        iw dev | grep Interface
    else
        echo "Error al cargar el módulo."
    fi
}

teardown() {
    echo "Descargando módulo mac80211_hwsim..."
    sudo modprobe -r mac80211_hwsim
    if [ $? -eq 0 ]; then
        echo "Módulo descargado con éxito."
    else
        echo "Error al descargar el módulo. Asegúrate de que hostapd esté detenido."
    fi
}

case $ACTION in
    "start")
        setup
        ;;
    "stop")
        teardown
        ;;
    *)
        echo "Uso: $0 {start|stop} [num_radios]"
        exit 1
        ;;
esac
