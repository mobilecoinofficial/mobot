#!/bin/bash

set -ex

# uncomment if migrations fail
# python /app/mobot/manage.py reset_db --router=default --noinput
python /app/mobot/manage.py makemigrations
python /app/mobot/manage.py migrate
python /app/mobot/manage.py createcachetable


uwsgi --ini /app/mobot/uwsgi.ini
