# Copyright (c) 2021 MobileCoin. All rights reserved.

"""
The entrypoint for the running MOBot.
"""

from django.core.management.base import BaseCommand
from django.conf import settings

from mobot_client.logger import SignalMessenger
from mobot_client.models import ChatbotSettings, Store
from mobot_client.core import MOBotSubscriber

import time
from django.core.management.base import BaseCommand
from django.conf import settings

from mobot_client.models import ChatbotSettings
from mobot_client.mobot import MOBot
from signald import Signal
from mobot_client.payments import MCClient, Payments
from signald_client import SignalLogger


class Command(BaseCommand):
    help = 'Run MOBot Client'

    def get_signal(self, cb_settings: ChatbotSettings, b64_public_address: str) -> Signal:
        store = cb_settings.store
        bot_avatar_filename = cb_settings.avatar_filename
        bot_name = cb_settings.name
        signal = Signal(str(store.source), socket_path=(settings.SIGNALD_ADDRESS, settings.SIGNALD_PORT))
        resp = signal.set_profile(
            display_name=bot_name,
            mobilecoin_address=b64_public_address,
            avatar_filename=cb_settings.avatar_filename,
            block=True
        )
        if resp.get("error"):
            assert False, resp
        return signal

    def get_payments(self, store: Store, messenger: SignalMessenger, signal: Signal, mcc: MCClient) -> Payments:
        return Payments(
            store=store,
            mobilecoin_client=mcc,
            signal=signal,
            messenger=messenger,
        )


    def handle(self, *args, **kwargs):
        cb_settings = ChatbotSettings.load()
        while not cb_settings.store:
            print("Awaiting settings... sleeping 60 seconds! Create a store and attach to ChatbotSettings to continue.")
            time.sleep(60)
            cb_settings.refresh_from_db()

        mcc = MCClient()
        signal = self.get_signal(cb_settings, mcc.b64_public_address)
        messenger = SignalMessenger(signal, cb_settings.store)
        payments = self.get_payments(
            store=cb_settings.store,
            messenger=messenger,
            signal=signal,
            mcc=mcc,
        )

        try:
            logger = SignalLogger(signal=signal, mcc=mcc)
            logger.run_chat(True, False)
            mobot = MOBotSubscriber(store=cb_settings.store,
                                    messenger=messenger,
                                    mcc=mcc,
                                    payments=payments)
            mobot.run_chat()
        except KeyboardInterrupt as e:
            print()
            pass
