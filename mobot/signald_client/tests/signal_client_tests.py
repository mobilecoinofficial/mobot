import unittest
from unittest import mock

from mobot.signald_client.tests import produce_messages
from mobot.signald_client import Signal, QueueSubscriber



class SignalClientTests(unittest.TestCase):

    def setUp(self):
        self.source = "+447441433907"

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
