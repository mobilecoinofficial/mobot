# Copyright (c) 2021 MobileCoin. All rights reserved.
import logging
import threading
from contextlib import contextmanager
from typing import Optional
from dataclasses import dataclass

from mobot_client.models import Store, Customer
from signald import Signal
from mobot_client.models.messages import Message, MobotResponse, Direction, MessageStatus, ProcessingError
from mobot_client.core.context import get_current_context, set_context, unset_context, ChatContext


class Responder:
    def __init__(self, message: Message):
        self._logger = logging.getLogger("MessageContext")
        self.message = message

    def __enter__(self):
        self._logger.info(f"Entering message response context to respond to {self.message}")
        self.message = self.message
        set_context(self.message)
        return self

    @property
    def customer(self):
        return self.message.customer

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._logger.info("Leaving message response context")
        try:
            if exc_type:
                self.message.status = MessageStatus.ERROR
                ProcessingError.objects.create(
                    message=self.message,
                    exception=str(exc_type),
                    tb=str(exc_tb)
                )
            else:
                self.message.status = MessageStatus.PROCESSED
            self.message.save()
        except Exception:
            self._logger.exception("Error leaving message context")
        finally:
            unset_context()


class SignalMessenger:
    def __init__(self, signal: Signal, store: Store):
        self.signal = signal
        self.store = store
        self.logger = logging.getLogger("SignalMessenger")

    def get_responder(self, message: Message, payments):

        class SignalResponder(Responder):
            def __init__(inner, *args, **kwargs):
                super().__init__(*args, **kwargs)

            def send_reply(inner, response: str, attachments=[]):
                self.log_and_send_message(response, attachments=attachments)

        return SignalResponder(message=message)

    def _log_and_send_message(self, customer: Customer, text: str, incoming: Optional[Message] = None, attachments=[]) -> Optional[MobotResponse]:

        response_message = Message(
            customer=customer,
            store=self.store,
            text=text,
            direction=Direction.SENT,
        )
        response_message.save()

        try:

            self.signal.send_message(recipient=customer.phone_number.as_e164,
                                     text=text,
                                     block=True,
                                     attachments=attachments)
            if incoming:
                response = MobotResponse.objects.create(
                    incoming=incoming,
                    outgoing_response=response_message,
                )
                return response
        except Exception as e:
            print(e)
            raise e

    def log_and_send_message(self, text: str, attachments=[]):
        ctx = get_current_context()
        incoming = ctx.message
        customer = ctx.message.customer
        self._log_and_send_message(customer, text, incoming, attachments)




    @staticmethod
    def log_received(message, customer, store) -> Message:
        incoming = Message(customer=customer, store=store, text=message.text,
                           direction=Direction.RECEIVED)
        incoming.save()
        return incoming