from django.test import TestCase, override_settings
from unittest import mock
from unittest.mock import MagicMock
import django
django.setup()

from mobot.apps.merchant_services.models import Merchant, Customer, Campaign, Product, ProductGroup, DropSession, Order, InventoryItem
from mobot.apps.merchant_services.tests.fixtures import StoreFixtures

from mobilecoin import Client
from mobot.signald_client.tests.fixtures import produce_message, produce_messages
from mobot.signald_client import Signal, QueueSubscriber
from ..chat_client import Mobot
from ..context import MessageContextBase, Message



def _test_handler(context: MessageContextBase):
    context.log_and_send_message(f"Hello {context.customer.name}!")


@override_settings(DEBUG=True, TEST=True)
class MobotTests(TestCase):

    def setUp(self):
        self.fixtures = StoreFixtures()


    def test_can_instantiate_mobot(self):
        campaign = self.fixtures.original_drop
        subscriber = QueueSubscriber(name="Mobot")
        with mock.patch.object(Signal, 'receive_messages', return_value=produce_messages(1)) as mock_method:
            signal_client = Signal(str(self.fixtures.merchant.phone_number))
            signal_client.register_subscriber(subscriber)
            mobilecoin_client = Client("foo")
            mobot = Mobot(signal=signal_client, mobilecoin_client=mobilecoin_client, campaign=self.fixtures.original_drop, store=self.fixtures.store)

    def test_can_register_and_handle_hello_world(self):
        campaign = self.fixtures.original_drop
        with mock.patch.object(Signal, 'receive_messages', return_value=[produce_message("hello", username=self.fixtures.cust_uk.name, source=str(self.fixtures.cust_uk.phone_number))]) as mock_method:
            signal_client = Signal(str(self.fixtures.merchant.phone_number))
            signal_client.send_message = MagicMock()
            mobilecoin_client = Client("foo")
            mobot = Mobot(signal=signal_client, mobilecoin_client=mobilecoin_client,
                          campaign=self.fixtures.original_drop, store=self.fixtures.store)
            mobot.register_handler("^hello$", _test_handler)
            mobot.run(max_messages=1)
            self.assertEqual(Message.objects.count(), 2)
            expected_message_strings = {f"{self.fixtures.cust_uk.phone_number}-hello-0", f"{self.fixtures.cust_uk.phone_number}-Hello {self.fixtures.cust_uk.name}!-1"}
            mobot_messages = {str(message) for message in Message.objects.all()}
            self.assertEqual(expected_message_strings, mobot_messages)

    def test_can_handle_unknown_match(self):
        with mock.patch.object(Signal, 'receive_messages', return_value=[produce_message("Blah", username=self.fixtures.cust_uk.name, source=str(self.fixtures.cust_uk.phone_number))]) as mock_method:
            signal_client = Signal(str(self.fixtures.merchant.phone_number))
            signal_client.send_message = MagicMock()
            mobilecoin_client = Client("foo")
            mobot = Mobot(signal=signal_client, mobilecoin_client=mobilecoin_client,
                          campaign=self.fixtures.original_drop, store=self.fixtures.store)
            mobot.register_handler("^hello$", _test_handler)
            mobot.run(max_messages=1)
            self.assertEqual(Message.objects.count(), 2)
            mobot_messages = [str(message) for message in Message.objects.all()]
            for message in mobot_messages:
                for line in message.split("\n"):
                    print(line)

    def test_can_show_privacy_policy(self):
        with mock.patch.object(Signal, 'receive_messages', return_value=[produce_message("p", username=self.fixtures.cust_uk.name, source=str(self.fixtures.cust_uk.phone_number))]) as mock_method:
            signal_client = Signal(str(self.fixtures.merchant.phone_number))
            signal_client.send_message = MagicMock()
            mobilecoin_client = Client("foo")
            mobot = Mobot(signal=signal_client, mobilecoin_client=mobilecoin_client,
                          campaign=self.fixtures.original_drop, store=self.fixtures.store)
            mobot.register_handler("^hello$", _test_handler)
            mobot.run(max_messages=1)
            self.assertEqual(Message.objects.count(), 2)
            mobot_messages = [message for message in Message.objects.all()]
            self.assertEqual(mobot_messages[0].direction, 0)
            self.assertEqual(mobot_messages[1].direction, 1)
            self.assertEqual(mobot_messages[1].text, "https://mobilecoin.com/privacy")


    def test_can_handle_inventory(self):
        pass

