#!/bin/bash
# Copyright (c) 2021 MobileCoin. All rights reserved.

set -e

python manage.py createcachetable

python manage.py makemigrations
python manage.py makemigrations mobot_client
python manage.py migrate
python manage.py migrate mobot_client

python manage.py check_migration

uwsgi --ini /app/uwsgi.ini
