# Copyright (c) 2021 MobileCoin. All rights reserved.
import logging
from typing import Optional

from mobot_client.models import Store, Customer
from signald import Signal
from mobot_client.models.messages import Message, MobotResponse, Direction, MessageStatus
from mobot_client.core.context import ChatContext


class SignalMessenger:
    def __init__(self, signal: Signal, store: Store):
        self.signal = signal
        self.store = store
        self.logger = logging.getLogger("SignalMessenger")

    def _log_and_send_message(self, customer: Customer, text: str, incoming: Optional[Message] = None, attachments=[]) -> Optional[MobotResponse]:
        response_message = Message.objects.create(
            customer=customer,
            store=self.store,
            text=text,
            direction=Direction.SENT,
            status=MessageStatus.PROCESSED,
        )

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
        ctx = ChatContext.get_current_context()
        incoming = ctx.message
        customer = ctx.message.customer
        self._log_and_send_message(customer, text, incoming, attachments)
