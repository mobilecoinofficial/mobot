#!/bin/bash

set -e
export DJANGO_SETTINGS_MODULE="settings"
python /app/mobot/manage.py collectstatic --noinput
sleep 10
python /app/mobot/manage.py run_mobot_client
