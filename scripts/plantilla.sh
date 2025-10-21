#!/bin/bash

###############
# PREPARACION #
###############

if [ $(whoami) != "root" ]; then
	echo "Necesitas ser root"
	exit 1
fi

conf_file="/usr/local/JSBach/config/plantilla.conf"
[ -f $conf_file ] || touch $conf_file
source $conf_file

########
# MAIN #
########
case $1 in
	--start)
	
		;;	
	--stop)
		;;

	--config)
		case $1 in
			dhcp)
				;;
			
			manual)
				;;

			*)
				;;
		esac
		;;

	--status)
		;;

	*)
		echo "Argumento no válido."
		echo "Uso: ./plantilla.sh --[start|stop|config|status]"
		exit 1
		;;
esac

exit 0
