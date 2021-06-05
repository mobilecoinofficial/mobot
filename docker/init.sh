#!/usr/bin/env bash
start_cmd=$1

source /.venv/bin/activate

case $start_cmd in

  admin)
    exec /scripts/admin_start.sh
    ;;

  client)
    exec /scripts/mobot_client_start.sh
    ;;

  *)
    echo "Command must be either 'admin' or 'client'"
    ;;

esac