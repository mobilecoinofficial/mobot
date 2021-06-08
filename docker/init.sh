#!/usr/bin/env bash
start_cmd=$1

set -e
echo "Setting up env"
. /app_scripts/set_up_env.sh
for env_var in $(env); do
  export $env_var
done

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