#!/bin/bash

# Copyright (c) 2021 MobileCoin. All rights reserved.

set -e

python manage.py check_migration
python manage.py test

python manage.py run_mobot_client
