#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

source $SCRIPT_DIR/set_up_env.sh
source $SCRIPT_DIR/create_wallet.sh
source $SCRIPT_DIR/reset_admin.sh
source $SCRIPT_DIR/delete_dbs.sh

ENV_FILE=$(output_env)
export ENV_FILE

CMD=$1

case $CMD in

  reset-admin)
    reset_admin
    ;;

  delete_dbs)
    delete_dbs
  ;;

  create_wallet)
    create_wallet
  ;;

  populate_merchant_and_products)
    exec python /app/mobot/manage.py merchant_admin --help
  ;;

  reset-all)
    echo "Resetting all and provisioning wallet";
    delete_dbs && echo "flushed dbs" && \
    create_wallet && echo "created wallet" && \
    reset_admin $ADMIN_USERNAME && echo "admin reset" && \
    python /app/module/manage.py merchant_admin --help && echo "merchants populated" && \
    echo "All done resetting everything"
  ;;

  *)
    echo "Command $CMD not valid"
    ;;

esac