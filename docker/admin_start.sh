#!/bin/bash

set -e

pipenv run -c python manage.py createcachetable

pipenv run -c python manage.py migrate

pipenv run -c uwsgi --ini /app/uwsgi.ini
