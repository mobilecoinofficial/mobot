#!/bin/bash

set -x



python /app/mobot/manage.py createcachetable
# python /app/mobot/manage.py merchant_admin


#/app/mobot/app_scripts/admin.sh create_wallet


uwsgi --ini /app/mobot/uwsgi.ini
