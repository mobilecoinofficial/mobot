#!/bin/bash

python /app/mobot/manage.py collectstatic --noinput
sleep 10
python /app/mobot/manage.py run_mobot_client
