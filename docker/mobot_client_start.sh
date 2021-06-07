#!/bin/bash

set -e
python /app/mobot/manage.py collectstatic --noinput
python /app/mobot/manage.py run_mobot_client
