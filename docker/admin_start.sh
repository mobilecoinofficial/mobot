# Copyright (c) 2021 MobileCoin. All rights reserved.

#!/bin/bash

set -e

python manage.py createcachetable

python manage.py migrate

uwsgi --ini /app/uwsgi.ini
