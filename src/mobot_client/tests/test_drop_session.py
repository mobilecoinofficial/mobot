# Copyright (c) 2021 MobileCoin. All rights reserved.
import logging
import uuid
from typing import List
from unittest.mock import MagicMock

import mc_util

from decimal import Decimal

from django.test import LiveServerTestCase

from mobot_client.chat_strings import ChatStrings
from mobot_client.core.subscriber import MOBotSubscriber
from mobot_client.logger import SignalMessenger
from mobot_client.tests.factories import StoreFactory, CustomerFactory, DropFactory, BonusCoinFactory
from mobot_client.models import Store, Customer
from mobot_client.models.messages import Message, Payment, PaymentStatus, Direction
from mobot_client.payments import MCClient, Payments
from mobot_client.tests.mock import TestMessage, MockSignal, MockMCC, mock_signal_message_with_receipt
from mobot_client.tests.test_messages import AbstractMessageTest
from signal_logger import SignalLogger


class DropSessionTest(AbstractMessageTest):

    def test_can_start_drop(self):
        customer = CustomerFactory.create()
        drop = DropFactory.create(store=self.store)
        bonus_coins = BonusCoinFactory.create(drop=drop)
        amount_pmob = int(Decimal("1e12"))
        self.create_incoming_message(customer=customer, store=self.store, text="Hi")
        self.subscriber.run_chat(process_max=1)
        received = Message.objects.filter(direction=Direction.RECEIVED)
        self.assertEqual(received.count(), 1)
        self.assertEqual(Message.objects.filter(direction=Direction.RECEIVED).first().text, "Hi")
        replies = Message.objects.filter(direction=Direction.SENT)
        self.assertEqual(replies.count(), 3)
        expected_responses = [
            ChatStrings.AIRDROP_DESCRIPTION,
            ChatStrings.AIRDROP_INSTRUCTIONS,
            ChatStrings.READY
        ]
        self.check_replies(messages=replies, expected_replies=expected_responses)
        self.assertEqual(customer.active_drop_sessions().filter(drop__store=self.store).count(), 1)




