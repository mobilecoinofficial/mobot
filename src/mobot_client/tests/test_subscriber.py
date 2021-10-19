# Copyright (c) 2021 MobileCoin. All rights reserved.
<<<<<<< HEAD
import timeit
=======
>>>>>>> dev
from mobot_client.core.context import ChatContext
from mobot_client.tests.factories import StoreFactory, CustomerFactory, DropFactory, BonusCoinFactory
from mobot_client.models.messages import Message, Payment, PaymentStatus, Direction
from mobot_client.tests.test_messages import AbstractMessageTest


class SubscriberTestCase(AbstractMessageTest):
    """Test whether subscriber can pick up on messages in the DB"""

    def test_subscriber(self):
        customer = CustomerFactory.create()
        drop = DropFactory.create(store=self.store)
<<<<<<< HEAD
        self.create_incoming_message(customer=customer, text="test")
=======
        self.create_incoming_message(customer=customer, store=self.store, text="test")
>>>>>>> dev
        TEST_RESPONSE = "Message Received!"

        def test_handler(ctx: ChatContext):
            print("Asserting received the right text")
            self.assertEqual(ctx.message.text, "test")
            self.assertEqual(ctx.message.direction, Direction.RECEIVED)
            print("Asserting the correct customer is derived")
            self.assertEqual(ctx.customer, customer)
            self.messenger.log_and_send_message(TEST_RESPONSE)

        self.subscriber.register_chat_handler("test", test_handler)
        self.subscriber.run_chat(process_max=1)
        received = Message.objects.filter(direction=Direction.RECEIVED)
        self.assertEqual(received.count(), 1)
        self.assertEqual(Message.objects.filter(direction=Direction.RECEIVED).first().text, "test")
        replies = Message.objects.filter(direction=Direction.SENT)
        self.assertEqual(replies.count(), 1)
        expected_responses = [
            TEST_RESPONSE
        ]
        self.check_replies(messages=replies, expected_replies=expected_responses)

    def test_subscriber_acknowledges_payment(self):
        customer = CustomerFactory.create()
        drop = DropFactory.create(store=self.store)
<<<<<<< HEAD
        self.create_incoming_message(customer=customer, text="test")
=======
        self.create_incoming_message(customer=customer, store=self.store, text="test")
>>>>>>> dev
        TEST_RESPONSE = "Message Received!"

        def test_handler(ctx: ChatContext):
            print("Asserting received the right text")
            self.assertEqual(ctx.message.text, "test")
            self.assertEqual(ctx.message.direction, Direction.RECEIVED)
            print("Asserting the correct customer is derived")
            self.assertEqual(ctx.customer, customer)
            self.messenger.log_and_send_message(TEST_RESPONSE)

        self.subscriber.register_chat_handler("test", test_handler)
        self.subscriber.run_chat(process_max=1)
        received = Message.objects.filter(direction=Direction.RECEIVED)
        self.assertEqual(received.count(), 1)
        self.assertEqual(Message.objects.filter(direction=Direction.RECEIVED).first().text, "test")
        replies = Message.objects.filter(direction=Direction.SENT)
        self.assertEqual(replies.count(), 1)
        expected_responses = [
            TEST_RESPONSE
        ]
<<<<<<< HEAD
        self.check_replies(messages=replies, expected_replies=expected_responses)
=======
        self.check_replies(messages=replies, expected_replies=expected_responses)
>>>>>>> dev
