import unittest
import pytest
from pytest_mock import class_mocker
from unittest import mock
from mobot.signald_client.types import Message
from mobot.signald_client import Signal, QueueSubscriber
from uuid import uuid4
from decimal import Decimal


# def _signald_to_fullservice(receipt):
#     return {
#         "object": "receiver_receipt",
#         "public_key": receipt['txo_public_key'],
#         "confirmation": receipt['txo_confirmation'],
#         "tombstone_block": str(receipt['tombstone']),
#         "amount": {
#             "object": "amount",
#             "commitment": receipt['amount_commitment'],
#             "masked_value": str(receipt['amount_masked'])
#         }
#     }


def produce_message(text_base: str = "Hello ", source="+447441433907", payment_amt: Decimal = 0) -> Message:
    payment = None if not payment_amt else dict(
        txo_public_key="A_public_key!",
        txo_confirmation="SomeConfirmation",
        amount_commitment=str(payment_amt),
        amount_masked=str(payment_amt),
    )
    return Message(
        username="Greg",
        source=source,
        payment=payment,
        text=f"{text_base} + {uuid4()}"
    )


def produce_messages(num_messages=10):
    for _ in range(num_messages):
        yield produce_message()


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

    def test_can_register_subscriber(self):
        subscriber = QueueSubscriber(name="Mobot")
        with mock.patch.object(Signal, 'receive_messages', return_value=produce_messages()) as mock_method:
            signal_client = Signal(self.source)
            signal_client.register_subscriber(subscriber)
            signal_client.run_chat(True)

        self.assertEqual(subscriber.size(), 10)
