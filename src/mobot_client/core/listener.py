# Copyright (c) 2021 MobileCoin. All rights reserved.

import threading
import logging
import sys
import signal
from collections import defaultdict
from typing import Iterator, Callable, List
from concurrent.futures import ThreadPoolExecutor, Future, as_completed

from signald.types import Message as SignalMessage
from signald_client import Signal
from django.conf import settings
from django.db.models import QuerySet

from mobot_client.models import Message, Store
from mobot_client.payments import MCClient


class MobotListener:
    def __init__(self, mcc: MCClient, signal_client: Signal, store: Store):
        self._mcc = mcc
        self._signal = signal_client
        self._logger = logging.getLogger("SignalListener")
        self._store = store
        self._run = True
        self._chat_handlers = []
        self._payment_handlers = []
        self._executor = ThreadPoolExecutor(max_workers=5)
        self._futures: List[Future] = []
        self._timeout = settings.SIGNALD_PROCESS_TIMEOUT
        self._signal.register_handler("", self.receive_message)

    @staticmethod
    def receive_message(self, signal_message: SignalMessage) -> Message:
        return Message.objects.create_from_signal(self._store, self._mcc, signal_message)

    def _messages(self) -> QuerySet[Message]:
        return Message.objects.not_processing()

    def _stop_handler(self, sig, frame):
        if sig:
            self._run = False
            self._logger.error(f"Interrupt called! Finishing message processing with a timeout of 20 seconds.")
        completed_futures = as_completed(self._futures, timeout=self._timeout)
        for future in completed_futures:
            self._logger.debug(f"Completed future {future}")
        sys.exit(0)

    def listen(self) -> Iterator[Message]:
        self._logger.debug("Registering interrupt handler...")
        signal.signal(signal.SIGINT, self._stop_handler)
        signal.signal(signal.SIGQUIT, self._stop_handler)
        messages_iterator = self._signal.receive_messages()
        while self._run:
            message = next(messages_iterator)
            self._logger.info(f"Receiving message \n {message}")
            if received := self._messages().first():
                yield received
