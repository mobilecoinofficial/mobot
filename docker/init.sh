#!/usr/bin/env bash
start_cmd=$1

source /.venv/bin/activate
export DATABASE_URL="postgres://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
echo $DATABASE_URL

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