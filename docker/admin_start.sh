#!/bin/bash

set -ex

if [[ "${MAKE_ADMIN:-false}" == true ]]; then
  echo "Starting admin with password ${ADMIN_PASSWORD}"
  echo "from django.contrib.auth.models import User; User.objects.create_superuser('greg', 'greg@mobilecoin.com', '$ADMIN_PASSWORD')" | python /app/mobot/manage.py shell
fi

# uncomment if migrations fail
if [[ "${FLUSH:-false}" == "true" ]]; then
  python /app/mobot/manage.py reset_db --router=default --noinput
fi

python /app/mobot/manage.py makemigrations payment_service
python /app/mobot/manage.py makemigrations merchant_services
python /app/mobot/manage.py migrate payment_service
python /app/mobot/manage.py migrate merchant_services
python /app/mobot/manage.py migrate auth
python /app/mobot/manage.py migrate
python /app/mobot/manage.py createcachetable

uwsgi --ini /app/mobot/uwsgi.ini
