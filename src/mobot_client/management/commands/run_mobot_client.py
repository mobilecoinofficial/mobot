# Copyright (c) 2021 MobileCoin. All rights reserved.

"""
The entrypoint for the running MOBot.
"""
import time
from argparse import ArgumentParser
from asyncio import Task
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio

from django.core.management.base import BaseCommand
from django.conf import settings
from django.db.models.signals import post_save, pre_delete
import django.db.models.signals as db_signals
from django.dispatch import receiver
from signald import Signal


from mobot_client.payments import MCClient, Payments
from signal_logger import SignalLogger

from mobot_client.logger import SignalMessenger
from mobot_client.models import ChatbotSettings, Store
from mobot_client.models.messages import Message
from mobot_client.core.subscriber import MOBotSubscriber



class Command(BaseCommand):
    help = 'Run MOBot Client'

    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument(
            '-l',
            '--listen',
            action='store_true',
            default=True
        )
        parser.add_argument(
            '-s',
            '--subscribe',
            action='store_true',
            default=True
        )

    def get_signal(self, cb_settings: ChatbotSettings, b64_public_address: str) -> Signal:
        store = cb_settings.store
        bot_avatar_filename = cb_settings.avatar_filename
        bot_name = cb_settings.name
        signal = Signal(str(store.phone_number), socket_path=(settings.SIGNALD_ADDRESS, int(settings.SIGNALD_PORT)))
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
        listen = kwargs.get('listen')
        subscribe = kwargs.get('subscribe')

        mcc = MCClient()
        signal = self.get_signal(cb_settings, mcc.b64_public_address)
        messenger = SignalMessenger(signal, cb_settings.store)
        print("Got messenger!")
        payments = self.get_payments(
            store=cb_settings.store,
            messenger=messenger,
            signal=signal,
            mcc=mcc,
        )
        futures = []

        try:
            loop = asyncio.get_event_loop()
            logger = SignalLogger(signal=signal, mcc=mcc)
            mobot = MOBotSubscriber(store=cb_settings.store,
                                    messenger=messenger,
                                    mcc=mcc,
                                    payments=payments)
            with ThreadPoolExecutor() as pool:
                if listen:
                    listen_task = pool.submit(logger.listen, True, True)
                if subscribe:
                    subscribe_task = pool.submit(mobot.run_chat)

            for fut in as_completed(futures):
                print(fut.result())

        except KeyboardInterrupt as e:
            print()
            pass
