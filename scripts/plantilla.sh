#!/bin/bash

###############
# PREPARACION #
###############

if [ $(whoami) != "root" ]; then
	echo "Necesitas ser root"
	exit 1
fi

conf_file="/usr/local/JSBach/config/ifwan.conf"

[ -f $conf_file ] || touch $conf_file

source $conf_file

function mod_conf_param () {
	param=$1
	new_value=$2

	if grep -q "^$param=" $conf_file; then
		sed -i 's/^'$param'=.*/'$param'='$new_value'/' $conf_file
	else
		echo "$param=$new_value" >> $conf_file
	fi
}

function del_conf_param () {
	param=$1

	sed -i '/^'$param'=/d' $conf_file
}



########
# MAIN #
########
case $1 in
	--start)
		if [ -n "$IFWAN" ] && [ "$MODE" == "dhcp" ]; then
			{ dhcpcd $IFWAN  && echo "DHCP activo"; } || echo "La tarjeta $IFWAN es desconocida o no se encuentra conectada."
		else
			echo "La variable IFWAN del fichero $conf_file no se encuentra configurada."
		fi
		;;

	--stop)
		if [ -n "$IFWAN" ] && [ "$MODE" == "manual" ]; then
			{ dhcpcd -k $IFWAN && echo "DHCP parado"; } || echo "La tarjeta $IFWAN es desconocida o no se encuentra conectada."
		else
			echo "La variable IFWAN del fichero $conf_file no se encuentra configurada."
		fi
		;;

	--config)
		shift 2
		case $1 in
			dhcp)
				if [ $# -ne 1 ]; then
					echo "Cantidad de argumentos incorrecta."
					echo "Uso: ./ifwan.sh --config dhcp <ifwan>"
					exit 1
				else
					mod_conf_param MODE dhcp
					mod_conf_param IFWAN $1

					del_conf_param IP
					del_conf_param PE
					del_conf_param DNS
				fi
				;;
			
			manual)
				if [ $# -ne 4 ]; then
					echo "Cantidad de argumentos incorrecta."
					echo "Uso: ./ifwan.sh --config manual <ifwan> <ip> <pe> <dns>"
					exit 1
				else
					mod_conf_param MODE manual
					mod_conf_param IFWAN $1
					mod_conf_param IP $2
					mod_conf_param PE $3
					mod_conf_param DNS $4

				fi
				;;

			*)
				echo "Argumento no válido."
				echo "Uso: ./ifwan.sh --config [dhcp|manual]"
				exit 1
				;;
		esac
		;;

	--status)
		;;

	*)
		echo "Argumento no válido."
		echo "Uso: ./ifwan.sh --[start|stop|config|status]"
		exit 1
		;;
esac

exit 0
