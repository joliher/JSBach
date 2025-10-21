#!/bin/bash

while true; do
	
	SCRIPTS_PATH=/usr/local/JSBach/scripts/

	echo "CLI>"	
	read iline
	
	read -a args <<< "$iline"

	if [ -z "${args[0]}" ]; then
		continue
	fi

	if ! [ -x "${args[0]}" ]; then
		if [ "${args[0]}" == "?" ]; then
			ls $SCRIPTS_PATH | sed 's/\.sh//'
		elif [ "${args[0]}" == "exit" ]; then
			exit 0
		else
			echo "No se ha encontrado el comando \"${args[0]}\" o no es ejecutable."
		fi
	else
		bash ${args[0]} ${args[@]:1}
	fi

done
