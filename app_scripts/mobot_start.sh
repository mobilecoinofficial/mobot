#!/usr/bin/env bash

CAMPAIGN_ID=$1
SHOP_ID=$2

python /app/mobot/manage.py collectstatic --noinput
sleep 10
python /app/mobot/manage.py run_chat --campaign-id $CAMPAIGN_ID --shop-id $SHOP_ID
