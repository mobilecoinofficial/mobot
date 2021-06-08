import os
import sys
import django

sys.path.append("/app/")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
django.setup()