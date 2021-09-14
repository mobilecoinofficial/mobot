# Copyright (c) 2021 MobileCoin. All rights reserved.
import logging
import random
import json
import socket
import time
from datetime import datetime
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterator, Tuple, Optional
from unittest.mock import AsyncMock, Mock, MagicMock, patch, create_autospec

from django.utils import timezone
from django.test import LiveServerTestCase
from phonenumbers import PhoneNumber, parse
from signald.types import Message as SignalMessage, Payment as SignalPayment

from mobot_client.core import MOBot
from mobot_client.tests.factories import StoreFactory, CustomerFactory
from mobot_client.models import Store, Customer
from mobot_client.models.messages import Message, MobotResponse, MessageDirection, Payment, PaymentStatus
from mobot_client.core.listener import MobotListener
from mobot_client.payments import MCClient
from signald_client import Signal


@dataclass
class TestMessage:
    text: str
    payment: Optional[int]
    phone_number: PhoneNumber
    timestamp: float = timezone.now().timestamp()


class ListenerTest(LiveServerTestCase):

    @patch('mobot_client.payments.MCClient', autospec=True)
    def setUp(self, mcc: MCClient) -> None:
        self.store: Store = StoreFactory.create()
        self.customer: Customer = CustomerFactory.create()
        self.logger = logging.getLogger('ListenerTest')
        self.mcc = mcc
        self._mock_patch_mcc(mcc)

    def _mock_signal_messages(self, messages: Iterator[TestMessage]):
        for test_message in messages:
            if not test_message.timestamp:
                time.sleep(0.3)
            yield SignalMessage(
                text=test_message.text,
                username=str(test_message.phone_number),
                source=dict(number=str(test_message.phone_number)),
                timestamp=timezone.now().timestamp(),
            )

    def signal(self, messages: Iterator[Tuple[PhoneNumber, str]] = []) -> Signal:
        signal = Signal(str(self.store.phone_number), multithreaded=False)
        with patch('socket.socket', autospec=True) as sock:
            signal._get_socket = create_autospec(signal._get_socket, return_value=sock)
        signal.sent_messages = []
        signal.set_profile = MagicMock(return_value={})

        def store_sent(recipient, text, block=None, attachments=None):
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

    def _mock_patch_mcc(self, mcc: MCClient) -> MCClient:
        mcc.logger = self.logger
        mcc.public_address = "foo"
        mcc.submit_transaction.return_value = random.randint(0, 10000000000000000)
        mcc.get_txo.return_value = "Happy"
        mcc.account_id = "12345"
        mcc.build_transaction.return_value = "proposal"
        mcc.create_receiver_receipts.return_value = ["receipt1", "receipt2"]
        mcc.minimum_fee_pmob = 40000
        return mcc

    @patch('mobot_client.payments.MCClient', autospec=True)
    def test_listener(self, mcc: MCClient):
        self._mock_patch_mcc(mcc)
        signal = self.signal(messages=[TestMessage(phone_number=self.customer.phone_number, text=message, payment=None) for message in ["Hello", "World"]])
        listener = MobotListener(mcc, signal, self.store)
        signal.run_chat(True, break_on_stop=True)
        # Give ourselves time to insert
        signal.finish_processing()
        self.assertEqual(Message.objects.all().count(), 2)
        messages = list(Message.objects.all())
        for message in messages:
            self.assertEqual(message.customer, self.customer)
        self.assertEqual(messages[0].text, "Hello")
        self.assertEqual(messages[1].text, "World")

    def test_mobot_gets_message_from_queue(self):
        signal = self.signal(messages=[TestMessage(phone_number=self.customer.phone_number, text="HI MOBOT")])
        mobot = MOBot(bot_name="MOBot", bot_avatar_filename="icon.png", store=self.store, signal=signal, mcc=self.mcc)
        mobot.run_chat(break_on_stop=True, break_after=1)
        responses = MobotResponse.objects.filter(incoming_message__customer=self.customer).all()
        self.assertEqual(responses.count(), 1)