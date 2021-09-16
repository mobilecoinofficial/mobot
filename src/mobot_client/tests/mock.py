# Copyright (c) 2021 MobileCoin. All rights reserved.

import attr
import uuid
import logging
from collections import defaultdict
from typing import Optional, Iterator, Union, List
from decimal import Decimal

from django.utils import timezone
from signald.types import Payment as SignalPayment, Message as SignalMessage

from mobot_client.models.messages import Message
from signald import Signal

from mobot_client.payments import MCClient


class MockMCC(MCClient):
    def __init__(self):
        self.logger = logging.getLogger("MCClient")
        self.receipt_status_responses = {}

    def _get_receipt(self, amount_pmob: int = int(Decimal("1e12"))) -> dict:
        """Create a bogus receipt with an amount"""
        full_service_receipt = {"txo":{
            "value_pmob": amount_pmob
        }}
        return full_service_receipt

    def add_mock_payment(self, amount_pmob: int) -> str:
        """Add a mock receipt response, returning a mock receipt ID"""
        mock_receipt = str(uuid.uuid4())
        self.receipt_status_responses[mock_receipt] = self._get_receipt(amount_pmob)
        return mock_receipt

    def get_receipt_status(self, receipt: str) -> dict:
        return self.receipt_status_responses[receipt]



@attr.s
class TestMessage:
    text = attr.ib(type=str)
    phone_number = attr.ib(type=str)
    timestamp = attr.ib(type=Optional[float], default=timezone.now().timestamp())
    payment = attr.ib(type=Optional[int], default=None)


def mock_signal_message_with_receipt(test_message: TestMessage, mcc: MockMCC):
    if test_message.payment:
        receipt = mcc.add_mock_payment(test_message.payment)
        payment = SignalPayment(
            note="a payment",
            receipt=receipt
        )
    else:
        payment = None

    return SignalMessage(
        text=test_message.text,
        username=str(test_message.phone_number),
        source=dict(number=str(test_message.phone_number)),
        timestamp=timezone.now().timestamp(),
        payment=payment
    )


class MockSignal(Signal):
    def __init__(self, test_messages: List[SignalMessage], store_number: str = "+14156665666"):
        self.received_messages = test_messages
        self.sent_messages = defaultdict(list)
        self.store_number = store_number

    def receive_messages(self) -> Iterator[SignalMessage]:
        for message in self.received_messages:
            yield message

    def send_message(
        self,
        recipient: Union[str, dict],
        text: str,
        block: bool = True,
        attachments: List[str] = [],
    ) -> None:
        self.sent_messages[recipient].append(TestMessage(text=text, phone_number=self.store_number))

    def send_read_receipt(self, recipient, timestamps, block: bool = True) -> None:
        pass