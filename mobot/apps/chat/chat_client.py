import logging
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
from typing import Iterator, Callable, Any
from chat_strings import *
import time
import re
from typing import Optional, Set

import phonenumbers
import mobilecoin
import pytz

from django.conf import settings
from django.utils import timezone


from mobot.apps.chat.models import Message, MessageDirection, MobotBot, MobotChatSession
from mobot.apps.merchant_services.models import Customer, CustomerStorePreferences, DropSession, Campaign, Store
from mobot.signald_client import Signal
from mobot.lib.signal import SignalCustomerDataClient
from mobot.signald_client.types import Message as SignalMessage
from mobot.signald_client.main import QueueSubscriber
from mobot.apps.chat.context import MessageContextFactory

class TransactionStatus(str, Enum):
    TRANSACTION_SUCCESS = "TransactionSuccess"
    TRANSACTION_PENDING = "TransactionPending"

RE_TYPE = type(re.compile(""))

class MobotMessage(str, Enum):
    YES = "y"
    NO = "n"
    CANCEL = "cancel"
    UNSUBSCRIBE = "unsubscribe"


class Mobot:
    def __init__(self, signal: Signal, store: Store, campaigns: Set[Campaign], mobilecoin_client: mobilecoin.Client):
        self.logger = logging.getLogger(f"Mobot-{self.store.id}")
        self.signal = signal
        self.campaigns = campaigns
        self.store = store
        self.mobilecoin_client = mobilecoin_client

        self.mobot: MobotBot = self.get_mobot_bot()
        self.message_context_factory = MessageContextFactory(self.mobot, self.logger)
        self.customer_data_client = SignalCustomerDataClient(signal=self.signal)
        self._subscriber = QueueSubscriber(self.name)
        self.signal.register_subscriber(self._subscriber)
        self._executor_futures = []
        self._chat_handlers = []
        self.register_handlers()

    def get_mobot_bot(self) -> MobotBot:
        created, _ = MobotBot.objects.get_or_create(name=self.name, store=self.store)

    def get_customer_from_message(self, message: SignalMessage) -> Customer:
        customer, _ = Customer.objects.get_or_create(phone_number=message.source)
        return customer

    def log_and_send_message(self, customer: Customer, text: str, session: MobotChatSession):
        sent_message = Message(
            customer=customer,
            store=Mobot.store,
            text=text,
            chat_session=session,
            direction=MessageDirection.MESSAGE_DIRECTION_SENT)
        sent_message.save()
        self.signal.send_message(str(customer.phone_number), text)

    def register_handler(self, regex: str, method: Callable[[SignalMessage], Any], order: int = 100):
        if not isinstance(regex, RE_TYPE):
            regex = re.compile(regex, re.I)
        self._chat_handlers.append((order, regex, method))
        # Use only the first value to sort so that declaration order doesn't change.
        self._chat_handlers.sort(key=lambda x: x[0])

    def unsubscribe_handler(self, message: SignalMessage):
        customer = self.get_customer_from_message(message)
        store_preferences = self.get_customer_store_preferences(customer)

        if not store_preferences.allows_contact:
            self.log_and_send_message(customer, message.source, NOT_RECEIVING_NOTIFICATIONS)
        else:
            store_preferences.allows_contact = False
            store_preferences.save()

            self.log_and_send_message(customer, message.source,
                                      NO_INFO_FUTURE_DROPS)

    def privacy_policy_handler(self, message: SignalMessage):
        self.log_and_send_message(message.source, self.store.privacy_policy_url)
        return

    def set_customer_preferences(self, customer: Customer, allow_contact: bool) -> CustomerStorePreferences:
        customer_prefs = CustomerStorePreferences.objects.get_or_create(customer=customer, store=self.store)
        customer_prefs.allows_contact = allow_contact
        customer_prefs.save()
        return customer_prefs

    def find_active_drop_for_customer(self, customer: Customer) -> Set[DropSession]:
        return set(DropSession.objects.filter(campaign=self.campaign, customer=customer).all())

    def get_chat_session_with_customer(self, customer: Customer) -> MobotChatSession:
        chat_session, _ = MobotChatSession.objects.get_or_create(mobot=self.mobot, customer=customer)
        return chat_session

    def handle_greet_customer(self, message: SignalMessage):
        customer = self.get_customer_from_message(message)
        greeting = GREETING.format(name=self.name, store=self.store, message_text=message.text)
        self.log_and_send_message(customer, greeting)

    def handle_start_conversation(self, message: SignalMessage):
        customer = self.get_customer_from_message(message)
        customer_store_preferences = self.get_customer_store_preferences(customer)
        chat_session = self.get_chat_session_with_customer(customer=customer)

    def _handle_chat(self, message: SignalMessage):
        for _, regex, func in self._chat_handlers:
            match = re.search(regex, message.text)
            if not match:
                continue
            try:
                return func(message)
            except Exception as e:  # noqa - We don't care why this failed.
                self.logger.error(e)
                continue

    def _save_message(self, message: SignalMessage):
        customer = self.get_customer_from_message(message)
        chat_session = self.get_chat_session_with_customer(customer)
        logged_message = Message(
            direction=MessageDirection.MESSAGE_DIRECTION_RECEIVED,
            customer=customer,
            text=message.text,
            chat_session=chat_session,
        )


    def _process_message(self, message: SignalMessage):
        customer = self.get_customer_from_message(message)
        chat_session = self.get_chat_session_with_customer(customer=customer)
        Message.objects.create(customer=customer, )
        self._handle_chat(message)

    def register_handlers(self):
        self.register_handler("unsubscribe", Mobot.unsubscribe_handler)
        self.register_handler("", self._greet_customer)
        self.register_handler("p", self.privacy_policy_handler)
        Mobot.signal.payment_handler(self.handle_payment)

    def run(self):
        self.signal.register_subscriber(self._per_cust_subscriber)
        with ThreadPoolExecutor(4) as executor:
            self._executor_futures.append(executor.submit(self.signal.run_chat, True))
            for message in self._subscriber.receive_messages():
                self._executor_futures.append(executor.submit(self._process_message, message))
        executor.shutdown(wait=True)
