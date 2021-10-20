# Copyright (c) 2021 MobileCoin. All rights reserved.
import logging
from decimal import Decimal
from typing import List, Union

from unittest.mock import MagicMock

import mc_util


from django.test import LiveServerTestCase

from mobot_client.core.subscriber import Subscriber
from mobot_client.logger import SignalMessenger
from mobot_client.tests.factories import StoreFactory
from mobot_client.models import Store, Customer
from mobot_client.models.messages import Message, Payment, PaymentStatus, Direction
from mobot_client.payments import Payments
from mobot_client.tests.mock import TestMessage, MockSignal, MockMCC


class AbstractMessageTest(LiveServerTestCase):
    def setUp(self) -> None:
        self.store: Store = StoreFactory.create()
        self.logger = logging.getLogger('ListenerTest')
        self.mcc = MockMCC()
        self.signal = MockSignal()
        self.messenger = SignalMessenger(self.signal, self.store)
        self.payments = self.get_payments()
        self.subscriber = Subscriber(store=self.store, messenger=self.messenger)

    def get_payments(self) -> Payments:
        payments = Payments(mobilecoin_client=self.mcc, store=self.store, messenger=self.messenger, signal=self.signal)
        payments.get_payments_address = MagicMock(autospec=True, return_value="123")
        payments.has_enough_funds_for_payment = MagicMock(autospec=True, return_value=True)
        return payments

    def create_incoming_message(self, customer: Customer, text: str = "", payment_mob: Decimal = 0) -> Message:
        if payment_mob > 0:
            payment = Payment.objects.create(
                amount_mob=payment_mob,
                status=PaymentStatus.TransactionSuccess,
                customer=customer,
            )
        else:
            payment = None
        return Message.objects.create(
            customer=customer,
            store=self.store,
            text=text if text else None,
            payment=payment,
            direction=Direction.RECEIVED,
        )

    def check_replies(self, messages: List[Union[Message, str]], expected_replies: List[str]):
        for message, expected_text in zip(messages, expected_replies):
            if isinstance(message, Message):
                message = message.text
            self.logger.info(f"\n--Received:\n{message}\n--Expected:\n{expected_text}")
            self.assertEqual(message, expected_text)

    def _compare_message(self, test_message: TestMessage, message: Message):
        self.logger.info(
            f"Checking if message phone number {message.customer.phone_number} equals input {test_message.phone_number}")
        self.assertEqual(test_message.phone_number, message.customer.phone_number)
        self.logger.info(f"Checking if message payment {message.payment.amount_mob} equals input {test_message.payment}")
        self.assertEqual(mc_util.pmob2mob(test_message.payment), message.payment.amount_mob)
        self.logger.info(f"Checking if message text {message.text} equals input {test_message.text}")
        self.assertEqual(test_message.text, message.text)
