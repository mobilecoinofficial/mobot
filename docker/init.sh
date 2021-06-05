source /.venv/bin/activate

cmd=$1

case $cmd in

  admin)
    exec /usr/local/bin/admin_start.sh
    ;;

  client)
    exec /usr/local/bin/mobot_client_start.sh
    ;;

  *)
    echo "Command must be either 'admin' or 'client'"
    ;;

esac