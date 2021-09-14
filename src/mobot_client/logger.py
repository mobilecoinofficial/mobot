# Copyright (c) 2021 MobileCoin. All rights reserved.
import logging
import threading
from contextlib import contextmanager
from typing import Optional
from dataclasses import dataclass

from mobot_client.models import Store
from signald_client import Signal
from mobot_client.models.messages import Message, MobotResponse, MessageDirection, MessageStatus, ProcessingError


class Responder:
    CONTEXT = threading.local()

    def __init__(self, message: Message):
        self._logger = logging.getLogger("MessageContext")
        self._context = Responder.CONTEXT
        self._context.message = message

    @property
    def message(self):
        return self._context.message

    def __enter__(self):
        self._logger.info(f"Entering message response context to respond to {self.message}")
        self._context.incoming_message = self.message
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._logger.info("Leaving message response context")
        if exc_type:
            self._context.message.status = MessageStatus.ERROR
            ProcessingError.objects.create(
                message=self.message,
                text=str(f"{exc_type}: {exc_tb}")
            )
        del self._context.message

    def _send(self, response: Message, attachments=[]):
        """This simply prints the message. For signal, it uses signal, of course."""
        self._logger.info(f"Dummy responder, responding to {self.message.customer.phone_number}:{self.message.text} - {response.text}")

    def _log_and_send_reply(self, response: Message, attachments=[]) -> MobotResponse:
        MobotResponse.objects.create(
            incoming=self.message,
            response=response,
        )
        self._send(response, attachments)

    def send_message_to_customer(self, body: str, attachments=[]):
        message = Message.objects.create(
            customer=self.message.customer,
            store=self.message.store,
            status=MessageStatus.NOT_PROCESSED,
            direction=MessageDirection.SENT,
        )
        self._log_and_send_reply(message)


class SignalMessenger:
    def __init__(self, signal: Signal, store: Store):
        self.signal = signal
        self.store = store
        self.logger = logging.getLogger("SignalMessenger")

    def get_responder(self, message: Message):

        class SignalResponder(Responder):
            def __init__(inner, *args, **kwargs):
                super().__init__(*args, **kwargs)

            def _send(inner, response: Message, attachments=[]):
                self.signal.send_message(str(response.customer.phone_number), response.text, attachments=attachments)

        return SignalResponder(message=message)

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