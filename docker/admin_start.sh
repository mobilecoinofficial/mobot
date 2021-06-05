#!/bin/bash

set -e

python mobot/manage.py createcachetable

python mobot/manage.py migrate

uwsgi --ini /app/mobot/uwsgi.ini
