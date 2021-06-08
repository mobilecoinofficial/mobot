#!/bin/bash

set -e

function admin_reset() {

  RESET_ADMIN="{$1:-false}"

  if [[ $RESET_ADMIN == true ]]; then
    python /app/mobot/manage.py migrate auth
    python /app/mobot/manage.py migrate
    python /app/mobot/manage.py flush --database auth_user #Truncate the db
    echo "from django.contrib.auth.models import User; User.objects.create_superuser('admin', 'admin@example.com', 'pass')" | python manage.py shell

  fi
  python /app/mobot/manage.py createcachetable
  uwsgi --ini /app/mobot/uwsgi.ini
  unset -e

  echo "ADMIN RESET SUCCESSFULLY"
}
