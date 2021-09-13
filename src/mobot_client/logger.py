# Copyright (c) 2021 MobileCoin. All rights reserved.
import logging
import threading
from contextlib import contextmanager
from typing import Optional
from dataclasses import dataclass

from mobot_client.models import Message, MessageDirection, MobotResponse


class SignalMessenger:
    CTX = threading.local()
    def __init__(self, signal, store):
        self.signal = signal
        self.store = store
        self.logger = logging.getLogger("SignalMessenger")
        self._context = SignalMessenger.CTX

    @contextmanager
    def message_context(self, message: Message):
        self._context.message = message
        yield self._context
        del self._context.message

    def send_message(self, text, attachments=[]):
        """Send a message, logging its response"""


    def log_and_send_message(self, customer, text, attachments=[]) -> MobotResponse:
        if hasattr(self._context, 'message'):
            incoming = self._context.message
            self.logger.info(f"Sending response to message {incoming}: {text}")
        else:
            incoming = None

        phone_number = customer.phone_number.as_e164

        response_message = Message(
            customer=customer,
            store=self.store,
            text=text,
            direction=MessageDirection.SENT,
        )
        response_message.save()

        try:
            self.signal.send_message(phone_number, text, attachments=attachments)
            response = MobotResponse.objects.create(
                incoming_message=incoming,
                incoming_payment=incoming.payment,
                response_message=response_message,
                response_payment=None
            )
            return response
        except Exception as e:
            print(e)
            raise e
            return e

    @staticmethod
    def log_received(message, customer, store) -> Message:
        incoming = Message(customer=customer, store=store, text=message.text,
                           direction=MessageDirection.RECEIVED)
        incoming.save()
        return incoming