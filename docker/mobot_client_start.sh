#!/bin/bash

set -e
python /app/mobot/manage.py collectstatic --noinput
