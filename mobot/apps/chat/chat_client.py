import logging
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
from typing import Iterator, Callable, Any
from chat_strings import *
import time
from collections import defaultdict
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


class MobotHandler:
    def __init__(self,
                 regex,
                 method: Callable[[MessageContextBase], Any],
                 order: int = 100,
                 drop_session_states: Set[DropSession.State] = set(),
                 chat_session_states: Set[MobotChatSession.State] = set()):
        self.regex = regex
        self._method = method
        self.drop_session_states = drop_session_states
        self.chat_session_states = chat_session_states
        self.order = order

    @property
    def all_states(self):
        return not self.drop_session_states and not self.chat_session_states # empty states

    def matches_context_states(self, context) -> bool:
        if self.all_states:
            return True
        elif not self.drop_session_states:
            if context.chat_session.state in self.chat_session_states:
                return True
        elif not self.chat_session_states:
            if context.drop_session.state in self.drop_session_states:
                return True
        elif context.drop_session.state in self.drop_session_states and context.chat_session.state in self.chat_session_states:
            return True
        return False

    def handle(self, context: MessageContextBase):
        self._method(context)



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
        self._chat_handlers = dict()
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

    def register_handler(self, regex: str, method: Callable[[MessageContextBase], Any], order: int = 100,
                               chat_session_states: Set[MobotChatSession.State] = set(),
                               drop_session_states: Set[DropSession.State] = set()):
        if not isinstance(regex, RE_TYPE):
            regex = re.compile(regex, re.I)
        handler = MobotHandler(regex, method, order=order, chat_session_states=chat_session_states, drop_session_states=drop_session_states)
        self._chat_handlers.append(handler)
        # Use only the first value to sort so that declaration order doesn't change.
        self._chat_handlers.sort(key=lambda x: x.order)

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

    def find_active_campaigns(self):
        Campaign.objects.filter(start_time__gte=timezone.now(), end_time__lte=timezone.now())

    def handle_already_greeted(self, context: MessageContextBase):
        context.log_and_send_message(ChatStrings.DIDNT_UNDERSTAND)

    def handle_start_conversation(self, context: MessageContextBase):
        if not self.campaign.is_active():
            context.log_and_send_message(ChatStrings.CAMPAIGN_INACTIVE)
        else:
            if context.customer.phone_number.country_code != context.campaign.number_restriction:
                context.log_and_send_message(ChatStrings.NOT_VALID_FOR_CAMPAIGN.format(context.campaign.number_restriction))

    def handle_greet_customer(self, context: MessageContextBase):
        context.log_and_send_message(ChatStrings.GREETING.format(campaign_description=context.campaign.description))
        context.chat_session.state = MobotChatSession.State.INTRODUCTION_GIVEN

    def _handle_chat(self, message: SignalMessage):
        # TODO: Would be great to cache these after they're hit... One day.
        with self.get_context_from_message(message) as context:
            matching_handlers = []
            for _, regex, handler in self._chat_handlers:
                regex_match = re.search(regex, message.text)
                if not regex_match:
                    continue
                if handler.matches_context_states(context):
                    matching_handlers.append(handler)
            # Run all handlers in order
            matching_handlers.sort(lambda handler: handler.order)
            for handler in matching_handlers:
                handler.handle(context)

    def register_handlers(self):
        self.register_handler("unsubscribe", self.unsubscribe_handler)
        self.register_handler("", self.handle_greet_customer, chat_session_states=MobotChatSession.State.NOT_GREETED, order=1) # First, say hello to the customer
        self.register_handler("", self.handle_start_conversation, chat_session_states=MobotChatSession.State.NOT_GREETED)
        self.register_handler("", self.handle_already_greeted, chat_session_states=MobotChatSession.State.INTRODUCTION_GIVEN)
        self.register_handler("p", self.privacy_policy_handler)
        Mobot.signal.payment_handler(self.handle_payment)

    def find_and_greet_targets(self, campaign):
        for customer in self.campaign.get_target_customers():
            CustomerStorePreferences.objects.filter(customer=customer, store_ref=campaign.store)
            self.logger.info("Reaching out to existing customers if they pass target validation")
            ctx = self.get_context_from_customer(customer)
            if ctx.drop_session.state == DropSession.State.CREATED:
                ctx.log_and_send_message(ChatStrings.GREETING.format(store=self.store,
                                                                     campaign=campaign,
                                                                     campaign_description=campaign.description))

    def run(self):
        self.signal.register_subscriber(self._subscriber)
        with ThreadPoolExecutor(4) as executor:
            self._executor_futures.append(executor.submit(self.signal.run_chat, True))
            for message in self._subscriber.receive_messages():
                self._executor_futures.append(executor.submit(self.find_and_greet_targets, self.campaign))
                self._executor_futures.append(executor.submit(self._handle_chat, message))
        executor.shutdown(wait=True)
