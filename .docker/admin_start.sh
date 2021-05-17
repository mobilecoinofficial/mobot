#!/bin/bash

set -e

python manage.py createcachetable

python manage.py migrate

uwsgi --ini /app/uwsgi.ini

# /usr/local/bin/python manage.py runserver 0.0.0.0:8000
