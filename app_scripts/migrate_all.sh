. /app/mobot/app_scripts/reset_admin.sh

# uncomment if migrations fail
if [ "${RESET_ALL}" == true ]; then
  echo "Resetting all schema"
  /app/mobot/app_scripts/reset_all.sh
  python /app/mobot/manage.py reset_schema --router=default --noinput
  python /app/mobot/manage.py reset_db --router=default --noinput
fi

if [ "${RESET_SCHEMA}" == true ]; then
  python /app/mobot/manage.py reset_schema --router=default --noinput
fi

set -a

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

python /app/mobot/manage.py makemigrations address
python /app/mobot/manage.py migrate address

python /app/mobot/manage.py makemigrations exchange
python /app/mobot/manage.py migrate exchange

python /app/mobot/manage.py makemigrations chat
python /app/mobot/manage.py migrate chat

python /app/mobot/manage.py makemigrations common
python /app/mobot/manage.py migrate common

python /app/mobot/manage.py makemigrations merchant_services
python /app/mobot/manage.py migrate merchant_services

python /app/mobot/manage.py makemigrations payment_service
python /app/mobot/manage.py migrate payment_service

python /app/mobot/manage.py makemigrations chat
python /app/mobot/manage.py migrate chat

python /app/mobot/manage.py migrate