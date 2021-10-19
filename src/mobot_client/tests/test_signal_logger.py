# Copyright (c) 2021 MobileCoin. All rights reserved.
import logging
from typing import List
from unittest.mock import MagicMock

import mc_util

from decimal import Decimal

from mobot_client.concurrency import AutoCleanupExecutor
from mobot_client.tests.factories import StoreFactory, CustomerFactory, DropFactory, BonusCoinFactory
from mobot_client.models.messages import Message
from mobot_client.tests.mock import TestMessage, MockSignal, MockMCC, mock_signal_message_with_receipt
from mobot_client.tests.test_messages import AbstractMessageTest
from signal_logger import SignalLogger


class SignalLoggerTest(AbstractMessageTest):

    def test_db_logging(self):
        """Ensure messages to signal are logged to DB"""
        amount_pmob = int(Decimal("1e12"))
        customer_1 = CustomerFactory.create()
        customer_2 = CustomerFactory.create()
        test_message_1 = TestMessage(phone_number=customer_1.phone_number, text="Hello World", payment=amount_pmob)
        test_message_2 = TestMessage(phone_number=customer_2.phone_number, text="Goodbye!",
                                     payment=2 * amount_pmob)
        test_messages = [mock_signal_message_with_receipt(message, self.mcc) for message in
                         [test_message_1, test_message_2]]
        signal = MockSignal(test_messages=test_messages)
        logger = SignalLogger(signal=signal, payments=self.payments)
        with AutoCleanupExecutor(max_workers=2) as pool:
            pool.submit(logger.listen, stop_when_done=True)
        print("Continuing test")
        self.assertEqual(Message.objects.all().count(), 2)
        messages = list(Message.objects.all())
        self._compare_message(test_message_1, messages[0])
        self._compare_message(test_message_2, messages[1])