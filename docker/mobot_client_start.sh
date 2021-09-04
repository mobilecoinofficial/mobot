#!/bin/bash

# Copyright (c) 2021 MobileCoin. All rights reserved.

set -e

/usr/local/bin/python manage.py check_migration && /usr/local/bin/python manage.py run_mobot_client
