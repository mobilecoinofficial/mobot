# Copyright (c) 2021 MobileCoin. All rights reserved.
import logging
import uuid
import mc_util

from decimal import Decimal

from django.test import LiveServerTestCase

from mobot_client.core.subscriber import MOBotSubscriber
from mobot_client.tests.factories import StoreFactory, CustomerFactory, DropFactory
from mobot_client.models import Store, Customer
from mobot_client.models.messages import Message
from mobot_client.payments import MCClient
from mobot_client.tests.mock import TestMessage, MockSignal, MockMCC, mock_signal_message_with_receipt
from signal_logger import SignalLogger


class MessageTest(LiveServerTestCase):

    def setUp(self) -> None:
        self.store: Store = StoreFactory.create()
        self.customer: Customer = CustomerFactory.create()
        self.customer_2: Customer = CustomerFactory.create()
        self.logger = logging.getLogger('ListenerTest')
        self.mcc = MockMCC()

    def _compare_message(self, test_message: TestMessage, message: Message):
        print(f"Checking if message phone number {message.customer.phone_number} equals input {test_message.phone_number}")
        self.assertEqual(test_message.phone_number, message.customer.phone_number)
        print(f"Checking if message payment {message.payment.amount_mob} equals input {test_message.payment}")
        self.assertEqual(mc_util.pmob2mob(test_message.payment), message.payment.amount_mob)
        print(f"Checking if message text {message.text} equals input {test_message.text}")
        self.assertEqual(test_message.text, message.text)

    def test_db_logging(self):
        """Ensure messages to signal are logged to DB"""
        amount_pmob = int(Decimal("1e12"))
        test_message_1 = TestMessage(phone_number=self.customer.phone_number, text="Hello World", payment=amount_pmob)
        test_message_2 = TestMessage(phone_number=self.customer_2.phone_number, text="Goodbye!", payment=2*amount_pmob)
        test_messages = [mock_signal_message_with_receipt(message, self.mcc) for message in [test_message_1, test_message_2]]
        signal = MockSignal(test_messages=test_messages)
        logger = SignalLogger(signal=signal, mcc=self.mcc)
        logger.listen(stop_when_done=True)
        self.assertEqual(Message.objects.all().count(), 2)
        messages = list(Message.objects.all())
        self._compare_message(test_message_1, messages[0])
        self._compare_message(test_message_2, messages[1])

    def test_response(self):
        drop = DropFactory.create(store=self.store)
        amount_pmob = int(Decimal("1e12"))
        test_hello_mobot = mock_signal_message_with_receipt(TestMessage(phone_number=self.customer.phone_number, text="Hi MOBot!", payment=None), self.mcc)
        signal = MockSignal(test_messages=[test_hello_mobot])
        logger = SignalLogger(signal=signal, mcc=self.mcc)
        logger.listen(stop_when_done=True)
        self.assertEqual(Message.objects.all().count(), 1)
        subscriber = MOBotSubscriber(store=self.store)
        subscriber.run_chat()


