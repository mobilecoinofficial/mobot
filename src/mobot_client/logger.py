# Copyright (c) 2021 MobileCoin. All rights reserved.
import logging

from mobot_client.models import Message, MessageDirection


class SignalMessenger:
    def __init__(self, signal, store):
        self.signal = signal
        self.store = store
        self.logger = logging.getLogger("SignalMessenger")

    def log_and_send_message(self, customer, source, text, attachments=[]):
        if isinstance(source, dict):
            source = source["number"]

        sent_message = Message(
            customer=customer,
            store=self.store,
            text=text,
            direction=MessageDirection.SENT,
        )
        sent_message.save()
        self.logger.info(f"Sending message to [{customer.phone_number}] - {text}")
        self.signal.send_message(str(source), text, attachments=attachments)

    @staticmethod
    def log_received(message, customer, store):
        incoming = Message(customer=customer, store=store, text=message.text,
                           direction=MessageDirection.RECEIVED)
        incoming.save()
