# Copyright (c) 2021 MobileCoin. All rights reserved.
from mobot_client.tests.factories import StoreFactory, CustomerFactory, DropFactory, BonusCoinFactory
from mobot_client.models.messages import Message, Payment, PaymentStatus, Direction
from mobot_client.tests.test_messages import AbstractMessageTest


class SubscriberTestCase(AbstractMessageTest):
    """Test whether subscriber can pick up on messages in the DB"""

    def test_subscriber(self):
        customer = CustomerFactory.create()
        drop = DropFactory.create(store=self.store)
        self.create_incoming_message(customer=customer, store=self.store, text="health")
        self.subscriber.run_chat(process_max=1)
        received = Message.objects.filter(direction=Direction.RECEIVED)
        self.assertEqual(received.count(), 1)
        self.assertEqual(Message.objects.filter(direction=Direction.RECEIVED).first().text, "health")
        replies = Message.objects.filter(direction=Direction.SENT)
        self.assertEqual(replies.count(), 1)
        expected_responses = [
            "Ok!"
        ]
        self.check_replies(messages=replies, expected_replies=expected_responses)