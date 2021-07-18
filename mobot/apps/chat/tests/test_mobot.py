import unittest

from django.test import TestCase, override_settings
from unittest import mock
from unittest.mock import MagicMock
import logging

import django
django.setup()

from mobot.apps.merchant_services.tests.fixtures import StoreFixtures

from mobilecoin import Client
from mobot.signald_client.tests.fixtures import produce_message, produce_messages
from mobot.signald_client import Signal, QueueSubscriber
from ..chat_client import Mobot
from ..context import MobotContext, Message



def _test_handler(context: MobotContext):
    context.log_and_send_message(f"Hello {context.customer.name}!")

def print_message(message: Message, logger: logging.Logger):
    for line in message.text.split("\n"):
        logger.debug(f" Message {'sent' if message.direction else 'received'}: {line}")



# FIXME: make sure the mock messages match the format of the actual signald messages

@override_settings(DEBUG=True, TEST=True)
class MobotTests(TestCase):

    def setUp(self):
        self.fixtures = StoreFixtures()
        self.logger = logging.getLogger("MobotTests")
        self.mobilecoin_client = Client("foo")

    def _get_mobot(self) -> Mobot:
        signal_client = Signal(str(self.fixtures.merchant.phone_number))
        signal_client.send_message = MagicMock()
        mobilecoin_client = Client("foo")
        mobot = Mobot(signal=signal_client, fullservice=mobilecoin_client,
                      campaign=self.fixtures.original_drop, store=self.fixtures.store)
        return mobot

    def test_can_instantiate_mobot(self):
        subscriber = QueueSubscriber(name="Mobot")
        with mock.patch.object(Signal, 'receive_messages', return_value=produce_messages(1)) as mock_method:
            mobot = self._get_mobot()

    def test_can_register_and_handle_hello_world(self):
        with mock.patch.object(Signal, 'receive_messages', return_value=[produce_message("hello", username=self.fixtures.cust_uk.name, source=str(self.fixtures.cust_uk.phone_number))]) as mock_method:
            mobot = self._get_mobot()
            mobot.register_handler(name="test", regex="^hello$", method=_test_handler)
            mobot.run(max_messages=1)
            for message in Message.objects.all():
                print(message.text)
            # self.assertEqual(Message.objects.count(), 2)

            expected_message_strings = {f"{self.fixtures.cust_uk.phone_number}-hello-0", f"{self.fixtures.cust_uk.phone_number}-Hello {self.fixtures.cust_uk.name}!-1"}
            mobot_messages = {str(message) for message in Message.objects.all()}
            self.assertEqual(expected_message_strings, mobot_messages)

    def test_can_handle_unknown_match(self):
        with mock.patch.object(Signal, 'receive_messages', return_value=[produce_message("Blah", username=self.fixtures.cust_uk.name, source=str(self.fixtures.cust_uk.phone_number))]) as mock_method:
            mobot = self._get_mobot()
            mobot.register_default_handlers()
            mobot.run(max_messages=1)
            for message in Message.objects.all():
                print_message(message, self.logger)
            self.assertEqual(Message.objects.count(), 3)

    def test_can_show_privacy_policy(self):
        with mock.patch.object(Signal, 'receive_messages', return_value=[produce_message("p", username=self.fixtures.cust_uk.name, source=str(self.fixtures.cust_uk.phone_number))]) as mock_method:
            mobot = self._get_mobot()
            mobot.register_default_handlers()
            mobot.run(max_messages=1)
            self.assertEqual(Message.objects.count(), 2)
            mobot_messages = [message for message in Message.objects.all()]
            self.assertEqual(mobot_messages[0].direction, 0)
            self.assertEqual(mobot_messages[1].direction, 1)
            self.assertEqual(mobot_messages[1].text, "https://mobilecoin.com/privacy")
            for message in mobot_messages:
                print_message(message, self.logger)

    def test_can_handle_inventory(self):
        with mock.patch.object(Signal, 'receive_messages', return_value=[produce_message("i", username=self.fixtures.cust_uk.name, source=str(self.fixtures.cust_uk.phone_number)), produce_message("i", username=self.fixtures.cust_uk.name, source=str(self.fixtures.cust_uk.phone_number))]) as mock_method:
            mobot = self._get_mobot()
            mobot.register_default_handlers()
            mobot.run(max_messages=1)
            mobot_messages = [message for message in Message.objects.all()]
            for message in mobot_messages:
                print_message(message, self.logger)

