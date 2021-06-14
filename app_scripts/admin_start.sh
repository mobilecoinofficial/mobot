#!/bin/bash

set -ex

# uncomment if migrations fail
# python /app/mobot/manage.py reset_db --router=default --noinput
set -a

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

python /app/mobot/manage.py makemigrations
python /app/mobot/manage.py migrate
python /app/mobot/manage.py createcachetable
python /app/mobot/manage.py update_rates


#/app/mobot/app_scripts/admin.sh create_wallet


uwsgi --ini /app/mobot/uwsgi.ini
