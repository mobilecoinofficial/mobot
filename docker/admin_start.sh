#!/bin/bash

set -e

python manage.py createcachetable

python manage.py migrate

uwsgi --ini /app/uwsgi.ini
