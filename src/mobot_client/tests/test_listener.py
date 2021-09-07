# Copyright (c) 2021 MobileCoin. All rights reserved.
import logging
import random
import json
import socket
import time
from datetime import datetime
from decimal import Decimal
from typing import Iterator, Tuple
from unittest.mock import AsyncMock, Mock, MagicMock, patch, create_autospec

from django.utils import timezone
from django.test import TestCase
from phonenumbers import PhoneNumber, parse
from signald.types import Message as SignalMessage, Payment as SignalPayment

from mobot_client.tests.factories import StoreFactory, CustomerFactory
from mobot_client.models import Message, MessageDirection, Payment, PaymentStatus, Store, Customer
from mobot_client.core.listener import MobotListener
from mobot_client.payments import MCClient
from signald_client import Signal


class ListenerTest(TestCase):

    def setUp(self) -> None:
        self.store: Store = StoreFactory.create()
        self.customer: Customer = CustomerFactory.create()
        self.logger = logging.getLogger('ListenerTest')

    def _mock_signal_messages(self, messages: Iterator[Tuple[PhoneNumber, str]]):
        for (number, text) in messages:
            time.sleep(0.3)
            yield SignalMessage(
                text=text,
                username=str(number),
                source=dict(number=str(number)),
                timestamp=timezone.now().timestamp(),
            )

    def signal(self, messages: Iterator[Tuple[PhoneNumber, str]] = []) -> Signal:
        signal = Signal(str(self.store.phone_number))
        with patch('socket.socket', autospec=True) as sock:
            signal._get_socket = create_autospec(signal._get_socket, return_value=sock)
        signal.sent_messages = []

        def store_sent(recipient, text, block=None, attachment=None):
            signal.sent_messages.append((recipient, text))

        signal.send_message = create_autospec(signal.send_message, return_value=None, side_effect=store_sent)
        signal.send_read_receipt = MagicMock()

        signal.receive_messages = MagicMock(
            return_value=self._mock_signal_messages(messages))

        return signal

    def _get_receipt(self, receipt, amount_pmob: int = int(Decimal("1e12"))):
        full_service_receipt = {
            "object": "receiver_receipt",
            "public_key": b"My Key".hex(),
            "confirmation": b"Confirmation".hex(),
            "tombstone_block": 12345,
            "amount": {
                "object": "amount",
                "commitment": b"Commitment".hex(),
                "masked_value": str(int(amount_pmob)),
            },
        }

    def _mock_mcc(self, mcc: MCClient) -> MCClient:
        mcc.logger = self.logger
        mcc.public_address = "foo"
        mcc.submit_transaction.return_value = random.randint(0, 10000000000000000)
        mcc.get_txo.return_value = "Happy"
        mcc.build_transaction.return_value = "proposal"
        mcc.create_receiver_receipts.return_value = ["receipt1", "receipt2"]
        return mcc


    @patch('mobot_client.payments.MCClient', autospec=True)
    def test_listener(self, mcc: MCClient):
        self._mock_mcc(mcc)
        signal = self.signal(messages=[(str(self.customer.phone_number), message) for message in ["Hello", "World"]])
        listener = MobotListener(mcc, signal, self.store)
        signal.run_chat(True, break_on_stop=True)
        self.assertEqual(Message.objects.count(), 2)
        messages = list(Message.objects.all())
        for message in messages:
            self.assertEqual(message.customer, self.customer)
        self.assertEqual(messages[0].text, "Hello")
        self.assertEqual(messages[1].text, "World")

