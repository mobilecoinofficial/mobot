# Copyright (c) 2021 MobileCoin. All rights reserved.

"""
WSGI config for mobot project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mobot.settings')

application = get_wsgi_application()
