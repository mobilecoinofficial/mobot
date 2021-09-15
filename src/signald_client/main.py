# Copyright (c) 2021 MobileCoin. All rights reserved.
# This code is copied from [pysignald](https://pypi.org/project/pysignald/) and modified to run locally with payments
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Protocol, Iterator

from signald import Signal as _Signal
from signald.types import Message as SignalMessage

from django.conf import settings
from mobot_client.models.messages import RawMessage, Message
from mobot_client.payments.client import MCClient


# We'll need to know the compiled RE object later.

RE_TYPE = type(re.compile(""))


class SignalReceiver(Protocol):
    def __call__(self, signal_message: SignalMessage) -> bool: ...


class DBSignal:
    '''A signal that logs to our DB instead of running callbacks'''

    def __init__(self, signal: _Signal, mcc: MCClient, *args, **kwargs):
        self.logger = logging.getLogger("SignalListener")
        self._mcc = mcc
        self._signal = signal
        self._pool = ThreadPoolExecutor(max_workers=settings.LISTENER_THREADS)
        self._futures = []

    def _parse_message(self, message, auto_send_receipts=True) -> Message:
        if not message.text or message.payment:
            self.logger.warning(f"Message contained no text or payment. Not processing. {message}")
            return False
        else:
            try:
                stored_message = Message.objects.create_from_signal(message)
                if message.payment:
                    payment = self._mcc.process_signal_payment(stored_message)
                    stored_message.payment = payment
                    stored_message.save()
                else:
                    payment = None
            except Exception as e:
                self.logger.exception("Exception storing message")
            else:
                # In case a message came from a group chat
                group_id = message.group_v2 and message.group_v2.get("id")
                # mark read and get that sweet filled checkbox
                try:
                    if auto_send_receipts and not group_id:
                        self._signal.send_read_receipt(recipient=message.source['number'], timestamps=[message.timestamp])
                except Exception as e:
                    print(e)
                    raise
                return stored_message

    def run_chat(self, auto_send_receipts=True):
        """
        Start the chat.
        """
        self.logger.debug("Registering interrupt handler...")
        for message in self._signal.receive_messages():
            self.logger.info(f"Signal received message {message}... Processing!")
            message = self._parse_message(message)
            self.logger.info(f"Stored message from {message}")

