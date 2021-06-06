"""
WSGI config for mobot_web project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/howto/deployment/wsgi/
"""

import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mobot.settings')

from django.core.wsgi import get_wsgi_application
import sys
sys.path.append("/app/")


application = get_wsgi_application()
