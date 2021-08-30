# Copyright (c) 2021 MobileCoin. All rights reserved.

"""
The entrypoint for the Django runserver command.
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from mobilecoin.client import Client

from mobot_client.models import ChatbotSettings
from mobot_client.mobot import MOBot
from signald_client import Signal


class Command(BaseCommand):
    help = 'Run MOBot Client'

    def handle(self, *args, **kwargs):
        try:
            store = ChatbotSettings.load().store
            signal = Signal(
                str(store.phone_number), socket_path=(settings.SIGNALD_ADDRESS, int(settings.SIGNALD_PORT))
            )
            mcc = Client(settings.FULLSERVICE_URL)
            mobot = MOBot(signal=signal, mcc=mcc)
            mobot.run_chat()
        except KeyboardInterrupt as e:
            print()
            pass
