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

ENV_FILE=$(output_env)

source ENV_FILE

case $start_cmd in

  admin)
    /scripts/admin_start.sh
    ;;

  client)
    /scripts/mobot_client_start.sh
    ;;

  *)
    echo "Command must be either 'admin' or 'client'"
    ;;

esac