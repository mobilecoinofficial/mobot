# Copyright (c) 2021 MobileCoin. All rights reserved.

"""
The entrypoint for the running MOBot.
"""
import time
from copy import deepcopy
from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import Process

from django.core.management.base import BaseCommand
from django.conf import settings
from signald import Signal

from mobot_client.drop_runner import DropRunner
from mobot_client.concurrency import AutoCleanupExecutor
from mobot_client.payments import MCClient, Payments
from signal_logger import SignalLogger

from mobot_client.logger import SignalMessenger
from mobot_client.models import ChatbotSettings, Store


class Command(BaseCommand):
    help = 'Run MOBot Client'

    def add_arguments(self, parser: ArgumentParser):
        """Somewhat meaningless for the moment, as they both default to true, but the listener logs messages
        from signal to the DB, and the subscriber runs a drop"""
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
        parser.add_argument(
            '-c',
            '--concurrency',
            type=int,
            default=1
        )

    def get_signal(self, cb_settings: ChatbotSettings, b64_public_address: str) -> Signal:
        store = cb_settings.store
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
        concurrency = kwargs.get('concurrency')

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
        processes = []

        try:
            logger = SignalLogger(signal=signal, payments=payments)
            with AutoCleanupExecutor(max_workers=8) as pool:
                if listen:
                    listen_task = Process(target=logger.listen, args=(True, True))
                    listen_task.start()
                    futures.append(pool.submit(listen_task.join))
                if subscribe:
                    mobot = DropRunner(store=cb_settings.store, messenger=messenger, payments=payments)
                    futures.append(pool.submit(mobot.run_chat))


            for fut in as_completed(futures):
                print(fut.done())

        except KeyboardInterrupt as e:
            print("Got an interrupt")
            pass
        finally:
            print("Done")
