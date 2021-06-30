from django.conf import settings
from mobot.apps.signald_client import Signal

signal = Signal(settings.STORE_NUMBER, socket_path=(settings.SIGNALD_ADDRESS, int(settings.SIGNALD_PORT)))
