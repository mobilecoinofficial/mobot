#!/bin/bash


function reset_admin {
  python /app/mobot/manage.py sqlmigrate auth
  python /app/mobot/manage.py migrate
  python /app/mobot/manage.py flush --database user #Truncate the db
  echo "from django.contrib.auth.models import User; User.objects.create_superuser('${ADMIN_USERNAME}', 'admin@example.com', 'pass')" | python /app/mobot/manage.py shell
  python /app/mobot/manage.py createcachetable

  echo "ADMIN RESET SUCCESSFULLY"
}