# Copyright (c) 2021 MobileCoin. All rights reserved.
import logging
from typing import Optional

from mobot_client.models import Message, MessageDirection, MobotResponse


class SignalMessenger:
    def __init__(self, signal, store):
        self.signal = signal
        self.store = store
        self.logger = logging.getLogger("SignalMessenger")

    def log_and_send_message(self, customer, text, incoming: Optional[Message] = None, attachments=[]) -> MobotResponse:
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
            return e

    @staticmethod
    def log_received(message, customer, store) -> Message:
        incoming = Message(customer=customer, store=store, text=message.text,
                           direction=MessageDirection.RECEIVED)
        incoming.save()
        return incoming
