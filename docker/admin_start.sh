#!/bin/bash

set -e

python /app/mobot/manage.py createcachetable

python /app/mobot/manage.py migrate

uwsgi --ini /app/mobot/uwsgi.ini
