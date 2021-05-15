import os

from django.core.management.base import BaseCommand
from signald_client import Signal

SIGNALD_ADDRESS = os.getenv("SIGNALD_ADDRESS", "127.0.0.1")
SIGNALD_PORT = os.getenv("SIGNALD_PORT", "15432")
STORE_NUMBER = os.environ["STORE_NUMBER"]
signal = Signal(STORE_NUMBER, socket_path=(SIGNALD_ADDRESS, int(SIGNALD_PORT)))

# catch all chat handler, will perform our own routing from here
@signal.chat_handler("")
def chat_router(message, match):
    print(message)

class Command(BaseCommand):
    help = 'Run MOBot Client'

    def handle(self, *args, **kwargs):
        try:
            signal.run_chat(True)
        except KeyboardInterrupt as e:
            print()
            pass
