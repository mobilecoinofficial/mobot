#!/usr/bin/env bash

start_cmd=$1
echo "Setting up env"
echo "Value of RESET_ALL: ${RESET_ALL:-false}"
export RESET_ALL

. /app/mobot/app_scripts/set_up_env.sh

ENV_FILE="/tmp/env.sh"

source $ENV_FILE

case $start_cmd in

  admin)
    /scripts/admin_start.sh
    ;;

  reset_admin)
    /scripts/reset_admin.sh
    ;;

  setup_hoodie)
    /scripts/set_up_hoodies.sh
    ;;

  chat_shell)
    /usr/bin/env bash
    ;;

  *)
    echo "Start command was: ${start_cmd}"
    echo "Command must be either 'admin' or 'reset_admin' or 'chat' or 'chat_shell' or 'admin'"
    exit 1
    ;;

esac