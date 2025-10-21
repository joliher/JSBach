#!/bin/bash

trap "rm -f /tmp/f; echo 'Tubería eliminada.'" EXIT

mkfifo /tmp/f
cat /tmp/f | /usr/local/JSBach/scripts/cli.sh 2>&1 | nc -kl 127.0.0.1 1234 > /tmp/f
