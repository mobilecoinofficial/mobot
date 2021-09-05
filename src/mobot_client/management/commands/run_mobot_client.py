# Copyright (c) 2021 MobileCoin. All rights reserved.

"""
The entrypoint for the running MOBot.
"""

from django.core.management.base import BaseCommand
from django.conf import settings


from mobot_client.models import ChatbotSettings
from mobot_client.core import MOBot
from signald_client import Signal

from mobot_client.payments import MCClient


class Command(BaseCommand):
    help = 'Run MOBot Client'

    def handle(self, *args, **kwargs):
        cb_settings = ChatbotSettings.load()
        store = cb_settings.store
        bot_avatar_filename = cb_settings.avatar_filename
        bot_name = cb_settings.name
        signal = Signal(str(store.phone_number), socket_path=(settings.SIGNALD_ADDRESS, settings.SIGNALD_PORT))
        mcc = MCClient()
        mobot = MOBot(bot_name=bot_name,
                      bot_avatar_filename=bot_avatar_filename,
                      store=store,
                      signal=signal,
                      mcc=mcc)
        mobot.run_chat()
