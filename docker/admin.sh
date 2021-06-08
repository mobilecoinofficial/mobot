#!/bin/bash

source ./delete_dbs.sh
source ./reset_admin.sh
source ./set_up_env.sh
source ./create_wallet.sh

CMD="{$1:-none}"

case $CMD in

  reset-admin)
    exec reset_admin $ADMIN_USERNAME
    ;;

  flush-dbs)
    exec flush_dbs
  ;;

  create_wallet)
    exec create_wallet
  ;;

  populate_merchant_and_products)
    exec python /app/mobot/manage.py merchant_admin --help
  ;;

  reset-all)
    echo "Resetting all and provisioning wallet";
    flush_dbs && echo "flushed dbs" && \
    create_wallet && echo "created wallet" && \
    reset_admin && echo "admin reset" && \
    python /app/module/manage.py merchant_admin --help && echo "merchants populated" && \
    echo "All done resetting everything"
  ;;

  *)
    echo "Command $CMD not valid"
    ;;

esac