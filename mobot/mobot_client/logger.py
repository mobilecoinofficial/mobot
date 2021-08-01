# Copyright (c) 2021 MobileCoin. All rights reserved.

import enum

from mobot_client.models import Message


class MessageDirection(enum.Enum):
    RECEIVED = 0
    SENT = 1


class SignalMessenger:

    def __init__(self, signal):
        self.signal = signal

    def log_and_send_message(self, customer, source, text, attachments=[]):
        if isinstance(source, dict):
            source = source['number']

        sent_message = Message(customer=customer, store=self.store, text=text, direction=MessageDirection.SENT)
        sent_message.save()
        self.signal.send_message(source, text, attachments=attachments)
