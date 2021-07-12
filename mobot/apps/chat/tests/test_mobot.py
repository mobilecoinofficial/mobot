import unittest
from unittest import mock


from mobot.apps.merchant_services.models import Merchant, Customer, Campaign, Product, ProductGroup, DropSession
from mobot.apps.drop.campaign_drop import Drop
from mobot.signald_client.tests.fixtures import produce_messages
from mobot.signald_client import Signal, QueueSubscriber


class MobotTests(unittest.TestCase):

    def setUp(self):
        self.merchant = Merchant

    def test_can_register_callback(self):
        import queue
        result_queue = queue.Queue()

        with mock.patch.object(Signal, 'receive_messages', return_value=produce_messages()) as mock_method:
                signal_client = Signal(self.source)
                signal_client.register_callback('print_got_message',
                                                lambda message: result_queue.put(f"Received message from {message.username}"))
                signal_client.run_chat(True)
        self.assertEqual(result_queue.qsize(), 10)
        self.assertEqual(result_queue.get(), "Received message from Greg")

    def test_can_register_subscriber_and_receive_messages(self):
        subscriber = QueueSubscriber(name="Mobot")
        with mock.patch.object(Signal, 'receive_messages', return_value=produce_messages(20)) as mock_method:
            signal_client = Signal(self.source)
            signal_client.register_subscriber(subscriber)
            signal_client.run_chat(True)

        self.assertEqual(subscriber.size(), 20)
        received = 0
        for message in subscriber.receive_messages(max_messages=10):
            self.assertEqual(message.source, self.source)
            received += 1
        self.assertEqual(received, subscriber.total_received)
