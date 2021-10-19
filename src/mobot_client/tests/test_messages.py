# Copyright (c) 2021 MobileCoin. All rights reserved.
import logging
from decimal import Decimal
<<<<<<< HEAD
from typing import List, Union
=======
from typing import List
>>>>>>> dev
from unittest.mock import MagicMock

import mc_util


from django.test import LiveServerTestCase

from mobot_client.core.subscriber import Subscriber
from mobot_client.logger import SignalMessenger
from mobot_client.tests.factories import StoreFactory
from mobot_client.models import Store, Customer
from mobot_client.models.messages import Message, Payment, PaymentStatus, Direction
from mobot_client.payments import Payments
from mobot_client.tests.mock import TestMessage, MockSignal, MockMCC, MockPayments


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

<<<<<<< HEAD
    def create_incoming_message(self, customer: Customer, text: str = "", payment_mob: Decimal = 0) -> Message:
=======
    def create_incoming_message(self, customer: Customer, store: Store = None, text: str = "", payment_mob: int = 0) -> Message:
        if not store:
            store = self.store
>>>>>>> dev
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
<<<<<<< HEAD
            store=self.store,
=======
            store=store,
>>>>>>> dev
            text=text if text else None,
            payment=payment,
            direction=Direction.RECEIVED,
        )

<<<<<<< HEAD
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
=======
    def check_replies(self, messages: List[Message], expected_replies: List[str]):
        for message, expected_text in zip(messages, expected_replies):
            print(f"Received: {message.text}. Expected: {expected_text}")
            self.assertEqual(message.text, expected_text)

    def _compare_message(self, test_message: TestMessage, message: Message):
        print(
            f"Checking if message phone number {message.customer.phone_number} equals input {test_message.phone_number}")
        self.assertEqual(test_message.phone_number, message.customer.phone_number)
        print(f"Checking if message payment {message.payment.amount_mob} equals input {test_message.payment}")
        self.assertEqual(mc_util.pmob2mob(test_message.payment), message.payment.amount_mob)
        print(f"Checking if message text {message.text} equals input {test_message.text}")
>>>>>>> dev
        self.assertEqual(test_message.text, message.text)
