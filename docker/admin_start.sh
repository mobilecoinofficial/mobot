#!/bin/bash
# Copyright (c) 2021 MobileCoin. All rights reserved.

set -e

python manage.py createcachetable

python manage.py migrate

python manage.py check_migration

uwsgi --ini /app/uwsgi.ini
