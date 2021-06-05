#!/bin/bash

set -e
python manage.py collectstatic --noinput
