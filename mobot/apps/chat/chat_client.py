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
from mobot.apps.chat.context import MessageContextFactory, MessageContextBase

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
    def __init__(self, signal: Signal, store: Store, campaign: Campaign, mobilecoin_client: mobilecoin.Client):
        self.logger = logging.getLogger(f"Mobot-{self.store.id}")
        self.signal = signal
        self.campaign = campaign
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

    def get_context_from_message(self, message: SignalMessage) -> MessageContextBase:
        context: MessageContextBase = self.message_context_factory.get_message_context(message)
        return context

    def get_context_from_customer(self, customer: Customer) -> MessageContextBase:
        context = self.message_context_factory.get_message_context(message=None, customer=customer)
        return context

    def get_mobot_bot(self) -> MobotBot:
        bot, _ = MobotBot.objects.get_or_create(name=self.name, store=self.store)
        return bot

    def get_customer_from_message(self, message: SignalMessage) -> Customer:
        customer, _ = Customer.objects.get_or_create(phone_number=message.source)
        return customer

    def register_handler(self, regex: str, method: Callable[[Message], Any], order: int = 100):
        if not isinstance(regex, RE_TYPE):
            regex = re.compile(regex, re.I)
        self._chat_handlers.append((order, regex, method))
        # Use only the first value to sort so that declaration order doesn't change.
        self._chat_handlers.sort(key=lambda x: x[0])

    def unsubscribe_handler(self, context: MessageContextBase):
        if not context.store_preferences.allows_contact:
            # User already inactive
            context.log_and_send_message(ChatStrings.NOT_RECEIVING_NOTIFICATIONS)
        else:
            context.store_preferences.allows_contact = False
            context.store_preferences.save()

            context.log_and_send_message(ChatStrings.NO_INFO_FUTURE_DROPS)

    def privacy_policy_handler(self, context: MessageContextBase):
        context.log_and_send_message(self.store.privacy_policy_url)
        return

    def set_customer_preferences(self, customer: Customer, allow_contact: bool) -> CustomerStorePreferences:
        customer_prefs = CustomerStorePreferences.objects.get_or_create(customer=customer, store=self.store)
        customer_prefs.allows_contact = allow_contact
        customer_prefs.save()
        return customer_prefs

    def handle_greet_customer(self, context: MessageContextBase):
        greeting = ChatStrings.GREETING.format(name=self.name, store=self.store, message_text=context.message.text)
        context.log_and_send_message(greeting)

    def handle_start_conversation(self, context: MessageContextBase):
        if not self.campaign.is_active():
            context.log_and_send_message(ChatStrings.CAMPAIGN_INACTIVE)
        else:


    def _handle_chat(self, message: SignalMessage):
        for _, regex, func in self._chat_handlers:
            match = re.search(regex, message.text)
            if not match:
                continue
            try:
                with self.get_context_from_message(message) as context:
                    return func(context)
            except Exception as e:  # noqa - We don't care why this failed.
                self.logger.error(e)
                continue

    def register_handlers(self):
        self.register_handler("unsubscribe", self.unsubscribe_handler)
        self.register_handler("", self._greet_customer)
        self.register_handler("p", self.privacy_policy_handler)
        Mobot.signal.payment_handler(self.handle_payment)

    def find_and_greet_targets(self):
        for customer in self.campaign.get_target_customers():
            ctx = self.get_context_from_customer(customer)
            if ctx.drop_session.state == DropSession.State.CREATED:
                ctx.log_and_send_message(ChatStrings.GREETING.format(store=self.store,
                                                                     campaign=self.campaign,
                                                                     campaign_description=self.campaign.description))

    def run(self):
        self.signal.register_subscriber(self._subscriber)
        with ThreadPoolExecutor(4) as executor:
            self._executor_futures.append(executor.submit(self.signal.run_chat, True))
            for message in self._subscriber.receive_messages():
                self._executor_futures.append(executor.submit(self._handle_chat, message))
        executor.shutdown(wait=True)
