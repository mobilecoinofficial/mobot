#!/bin/bash

set -e
pipenv run -c python manage.py collectstatic --noinput
