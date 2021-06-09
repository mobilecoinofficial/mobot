#!/usr/bin/env bash
start_cmd=$1

set -e
echo "Setting up env"

. /app/mobot/app_scripts/set_up_env.sh
. /app/mobot/app_scripts/create_wallet.sh
. /app/mobot/app_scripts/delete_dbs.sh
. /app/mobot/app_scripts/create_wallet.sh
. /app/mobot/app_scripts/reset_admin.sh
. /app/mobot/app_scripts/admin_start.sh

output_env

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