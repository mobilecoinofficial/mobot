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
from django.db import transaction

from mobot_client.models import Message, Store, Customer, MessageStatus
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

    @transaction.atomic
    def receive_message(self, signal_message: SignalMessage, *args) -> Message:
        self._logger.info(f"Listener received from signal: {signal_message}")
        if isinstance(signal_message.source, dict):
            number = signal_message.source['number']
        else:
            number = signal_message.source
        customer, _ = Customer.objects.get_or_create(phone_number=number)
        message = Message.objects.create_from_signal(store=self._store,
                                                     mcc=self._mcc,
                                                     customer=customer,
                                                     message=signal_message)
        self._logger.info(f"Listener logged to database {message}")

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

    def listen(self, break_on_stop=False):
        self._signal.run_chat(True, break_on_stop=break_on_stop)
