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

	sed -i 's/^'$param'=.*/'$param'=/' $conf_file
}



########
# MAIN #
########
case $1 in
	--start)
		{ ! [ -z $IFWAN ] && ! [ -z $MODE ]; } || { echo "WARN: Se debe hacer una configuración inicial del script." && exit 1; }

		if $(curl https://www.google.com &>/dev/null); then
			echo "ERROR: La tarjeta $IFWAN ya está activada."
			exit 1
		fi	
		case $MODE in
			dhcp)
				{ dhcpcd $IFWAN &>/dev/null  && echo "DHCP activo"; } || echo "La configuración DHCP en $IFWAN ha fallado."
				;;
			manual)
				ip l s dev $IFWAN up &>/dev/null && echo "Tarjeta UP"
				ip a a $IP/$MASC dev $IFWAN &>/dev/null && echo "IP configurada"
				ip r a default via $PE &>/dev/null && echo "Ruta DEFAULT configurada"

				if grep -q "^#DNS=" /etc/systemd/resolved.conf; then
					sed -i "s/^#DNS=.*/DNS=$DNS/" /etc/systemd/resolved.conf
				elif grep -q "^DNS=" /etc/systemd/resolved.conf; then
					sed -i "s/^DNS=.*/DNS=$DNS/" /etc/systemd/resolved.conf
				else
					echo "DNS=$DNS" >> /etc/systemd/resolved.conf
				fi

				systemctl restart systemd-resolved
				;;

		esac
		;;

	--stop)
		{ ! [ -z $IFWAN ] && ! [ -z $MODE ]; } || { echo "WARN: Se debe hacer una configuración inicial del script." && exit 1; }

		{
			{ dhcpcd -k $IFWAN &>/dev/null && echo "DHCP parado"; } || {
			       { 
				       ip a d $IP/$MASC dev $IFWAN &>/dev/null && echo "IP eliminada"; 
			       } && {
				       ip l s dev $IFWAN down &>/dev/null && echo "Tarjeta parada"; 
			       }; 
			}; 
		} || echo "ERROR: La interfaz $IFWAN ya se encuentra parada."
	;;

	--config)
		MODE=$2
		shift 2
		case $MODE in
			dhcp)
				if [ $# -ne 1 ]; then
					echo "Cantidad de argumentos incorrecta."
					echo "Uso: ./ifwan.sh --config dhcp <ifwan>"
					exit 1
				else
					mod_conf_param MODE dhcp
					mod_conf_param IFWAN $1

					del_conf_param IP
					del_conf_param MASC
					del_conf_param PE
					del_conf_param DNS
				fi
				;;
			
			manual)
				if [ $# -ne 4 ]; then
					echo "Cantidad de argumentos incorrecta."
					echo "Uso: ./ifwan.sh --config manual <ifwan> <ip>/<mascara> <pe> <dns>"
					exit 1
				else
					IFWAN=$1
					IP=$(echo $2 | cut -d "/" -f 1)
					MASC=$(echo $2 | cut -d "/" -f 2)
					PE=$3
					DNS=$4

					mod_conf_param MODE manual
					mod_conf_param IFWAN $IFWAN
					mod_conf_param IP $IP
					mod_conf_param MASC $MASC
					mod_conf_param PE $PE
					mod_conf_param DNS $DNS

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
		if [ -z $IFWAN ] || [ -z $MODE ]; then
		       echo "WARN: Se debe hacer una configuración inicial del script."
		       exit 1
		fi

		if curl https://www.google.com &>/dev/null; then
			echo "WAN ACTIVADA"
		else
		       	echo "WAN DESACTIVADA"
		fi

		;;

	*)
		echo "Argumento no válido."
		echo "Uso: ./ifwan.sh --[start|stop|config|status]"
		exit 1
		;;
esac

exit 0
