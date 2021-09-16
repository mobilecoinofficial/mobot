# Copyright (c) 2021 MobileCoin. All rights reserved.
import logging
import uuid

from decimal import Decimal

from django.test import LiveServerTestCase

from mobot_client.tests.factories import StoreFactory, CustomerFactory
from mobot_client.models import Store, Customer
from mobot_client.models.messages import Message
from mobot_client.payments import MCClient
from mobot_client.tests.mock import TestMessage, MockSignal, MockMCC, mock_signal_message_with_receipt
from signald_client import SignalLogger


class MessageTest(LiveServerTestCase):

    def setUp(self) -> None:
        self.store: Store = StoreFactory.create()
        self.customer: Customer = CustomerFactory.create()
        self.logger = logging.getLogger('ListenerTest')
        self.mcc = MockMCC()

    def test_db_logging(self):
        """Ensure messages to signal are logged to DB"""
        amount_mob = int(Decimal("1e12"))
        test_messages = [mock_signal_message_with_receipt(TestMessage(
            phone_number=self.customer.phone_number, text=message, payment=amount_mob), self.mcc) for message in ["Hello", "World"]]
        signal = MockSignal(test_messages=test_messages)
        logger = SignalLogger(signal=signal, mcc=self.mcc)
        logger.run_chat(stop_when_done=True)
        self.assertEqual(Message.objects.all().count(), 2)
        messages = list(Message.objects.all())
        for message in messages:
            self.assertEqual(message.customer, self.customer)
        self.assertEqual(messages[0].text, "Hello")
        self.assertEqual(messages[1].text, "World")

