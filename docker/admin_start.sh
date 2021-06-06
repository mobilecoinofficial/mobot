#!/bin/bash

set -ex


python /app/mobot/manage.py reset_db --router=default
python /app/mobot/manage.py makemigrations
python /app/mobot/manage.py migrate
python /app/mobot/manage.py createcachetable


uwsgi --ini /app/mobot/uwsgi.ini
