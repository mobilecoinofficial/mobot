#!/usr/bin/env bash

if [[ "${RESET_ALL:-false}" == true ]]; then
  python /app/mobot/manage.py makemigrations default
  python /app/mobot/manage.py migrate
  python /app/mobot/manage.py flush --database user #Truncate the db
  echo "from django.contrib.auth.models import User; User.objects.create_superuser('mcadmin', 'admin@mobilecoin.com', 'mcadmin')" | python /app/mobot/manage.py shell
  python /app/mobot/manage.py createcachetable

  echo "ADMIN RESET SUCCESSFULLY"
fi