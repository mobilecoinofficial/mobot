# Copyright (c) 2021 MobileCoin. All rights reserved.
from decimal import Decimal

from mobot_client.chat_strings import ChatStrings
from mobot_client.drop_runner import DropRunner
from mobot_client.tests.factories import CustomerFactory, DropFactory, BonusCoinFactory
from mobot_client.models.messages import Message, Direction
from mobot_client.tests.test_messages import AbstractMessageTest


class DropSessionTest(AbstractMessageTest):

    def test_can_start_drop(self):
        customer = CustomerFactory.create()
        drop = DropFactory.create(store=self.store)
        bonus_coins = BonusCoinFactory.create(drop=drop)
        amount_pmob = int(Decimal("1e12"))
        hello_message = self.create_incoming_message(customer=customer, store=self.store, text="Hi")
        self.subscriber = DropRunner(store=self.store, messenger=self.messenger, payments=self.payments)
        # Process a single message
        self.subscriber.run_chat(process_max=1)
        hello_replies = Message.objects.filter(direction=Direction.SENT, date__gt=hello_message.date)
        self.assertEqual(hello_replies.count(), 3)
        hello_expected_responses = [
            ChatStrings.AIRDROP_DESCRIPTION,
            ChatStrings.AIRDROP_INSTRUCTIONS,
            ChatStrings.READY
        ]
        self.check_replies(messages=hello_replies, expected_replies=hello_expected_responses)
        self.assertEqual(customer.active_drop_sessions().filter(drop__store=self.store).count(), 1)