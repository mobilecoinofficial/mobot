"""
WSGI config for mobot_web project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/howto/deployment/wsgi/
"""

import os
import sys
sys.path.append("/app/mobot/")
os.environ["DJANGO_SETTINGS_MODULE"] = "settings"

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
