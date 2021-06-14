#!/bin/bash

set -x

# uncomment if migrations fail
if [ "${RESET_ALL}" == true ]; then
  python /app/mobot/manage.py reset_schema --router=default --noinput
  python /app/mobot/manage.py reset_db --router=default --noinput
fi

if [ "${RESET_SCHEMA}" == true ]; then
  python /app/mobot/manage.py reset_schema --router=default --noinput
fi

set -a

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

python /app/mobot/manage.py makemigrations exchange
python /app/mobot/manage.py migrate exchange

python /app/mobot/manage.py makemigrations payment_service
python /app/mobot/manage.py migrate payment_service

python /app/mobot/manage.py makemigrations merchant_services
python /app/mobot/manage.py migrate payment_service

python /app/mobot/manage.py createcachetable
# python /app/mobot/manage.py merchant_admin


#/app/mobot/app_scripts/admin.sh create_wallet


uwsgi --ini /app/mobot/uwsgi.ini
