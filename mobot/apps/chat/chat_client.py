import logging
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
from typing import Iterator, Callable, Any
from chat_strings import *
import time
import re

import phonenumbers
import mobilecoin
import pytz

from django.conf import settings
from django.utils import timezone


from mobot.apps.chat.models import Message, MessageDirection
from mobot.apps.merchant_services.models import Customer, CustomerStorePreferences, DropSession, Campaign, Store
from mobot.signald_client import Signal
from mobot.lib.signal import SignalCustomerDataClient
from mobot.signald_client.types import Message
from mobot.signald_client.main import QueueSubscriber, MessageSubscriber

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
    def __init__(self, name: str, signal: Signal, store: Store, mobilecoin_client: mobilecoin.Client):
        self.logger = logging.getLogger("Mobot")
        self.signal = signal
        self.store = store
        self.mobilecoin_client = mobilecoin_client
        self.name = name
        self.customer_data_client = SignalCustomerDataClient(signal=self.signal)
        self._subscriber = QueueSubscriber(name)
        self.signal.register_subscriber(self._subscriber)
        self._executor_futures = []
        self._chat_handlers = []
        self.register_handlers()

    def get_customer_from_message(self, message: Message) -> Customer:
        customer, _is_new_customer = Customer.objects.get_or_create(phone_number=message.source)
        return customer

    def log_and_send_message(self, customer: Customer, text: str):
        sent_message = Message(customer=customer, store=Mobot.store, text=text,
                               direction=MessageDirection.MESSAGE_DIRECTION_SENT)
        sent_message.save()
        self.signal.send_message(str(customer.phone_number), text)

    def privacy_policy_handler(self, message, _match):
        customer, _is_new = Customer.objects.get_or_create(phone_number=message.source['number'])
        Mobot.log_and_send_message(customer, message.source, Mobot.store.privacy_policy_url)
        return

    def register_handler(self, regex: str, method: Callable[[Message, Customer], Any], order: int = 100):
        if not isinstance(regex, RE_TYPE):
            regex = re.compile(regex, re.I)
        self._chat_handlers.append((order, regex, method))
        # Use only the first value to sort so that declaration order doesn't change.
        self._chat_handlers.sort(key=lambda x: x[0])

    def unsubscribe_handler(self, message: Message, customer: Customer):
        store_preferences, _is_new = CustomerStorePreferences.objects.get_or_create(customer=customer,
                                                                                    store=self.store)

        if not store_preferences.allows_contact:
            self.log_and_send_message(customer, message.source, NOT_RECEIVING_NOTIFICATIONS)

        store_preferences.allows_contact = False
        store_preferences.save()

        self.log_and_send_message(customer, message.source,
                                  NO_INFO_FUTURE_DROPS)

    def set_customer_preferences(self, customer: Customer, allow_contact: bool):
        customer_prefs = CustomerStorePreferences(customer=customer, store=self.store,
                                                  allows_contact=allow_contact)
        customer_prefs.save()

    def find_active_drop_for_customer(self, customer: Customer) -> DropSession:
        return customer.offer_sessions.get(campaign=self.drop.campaign)

    def _greet_customer(self, customer: Customer, message: Message):
        greeting = GREETING.format(name=self.name, store=self.store, message_text=message.text)
        self.log_and_send_message(customer, greeting)

    def _handle_chat(self, message: Message, customer: Customer):
        for _, regex, func in self._chat_handlers:
            match = re.search(regex, message.text)
            if not match:
                continue
            try:
                return func(message, customer)
            except Exception as e:  # noqa - We don't care why this failed.
                self.logger.error(e)
                continue

    def _process_message(self, message: Message):
        customer = self.get_customer_from_message(message)
        self._handle_chat(message, customer)

    def register_handlers(self):
        self.register_handler("unsubscribe", Mobot.unsubscribe_handler)
        self.register_handler("", self._greet_customer)
        Mobot.signal.register_chat_handler("p", Mobot.privacy_policy_handler)
        Mobot.signal.payment_handler(self.handle_payment)

    def run(self):
        self.signal.register_subscriber(self._per_cust_subscriber)
        with ThreadPoolExecutor(4) as executor:
            self._executor_futures.append(executor.submit(self.signal.run_chat, True))
            for message in self._subscriber.receive_messages():
                self._executor_futures.append(executor.submit(self._process_message, message))
        executor.shutdown(wait=True)

