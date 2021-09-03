# Copyright (c) 2021 MobileCoin. All rights reserved.

"""
The entrypoint for the running MOBot.
"""

from django.core.management.base import BaseCommand
from mobot_client.mobot import MOBot


class Command(BaseCommand):
    help = 'Run MOBot Client'

    def handle(self, *args, **kwargs):
        try:
            mobot = MOBot()
            mobot.run_chat()
        except KeyboardInterrupt as e:
            print()
            pass
