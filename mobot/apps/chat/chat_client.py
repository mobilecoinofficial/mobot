import logging
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any
from handlers import *
import re
from typing import Set

import phonenumbers
import mobilecoin
import pytz

from django.conf import settings
from django.utils import timezone


from .models import Message, MessageDirection, MobotBot, MobotChatSession
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
        return self._method(context)


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
        self._empty_regex_chat_handlers = []
        self._nonempty_regex_chat_handlers = []
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
        if regex:
            if not isinstance(regex, RE_TYPE):
                regex = re.compile(regex, re.I)
        handler = MobotHandler(regex, method, order=order, chat_session_states=chat_session_states, drop_session_states=drop_session_states)
        if handler.regex:
            self._nonempty_regex_chat_handlers.append(handler)
        else:
            self._empty_regex_chat_handlers.append(handler)


    def set_customer_preferences(self, customer: Customer, allow_contact: bool) -> CustomerStorePreferences:
        customer_prefs = CustomerStorePreferences.objects.get_or_create(customer=customer, store=self.store)
        customer_prefs.allows_contact = allow_contact
        customer_prefs.save()
        return customer_prefs

    def find_active_campaigns(self):
        Campaign.objects.filter(start_time__gte=timezone.now(), end_time__lte=timezone.now())

    def _handle_chat(self, message: SignalMessage):
        # TODO: Would be great to cache these after they're hit... One day.
        with self.get_context_from_message(message) as context:
            matching_handlers = []
            empty_regex_handlers = [handler for handler in self._chat_handlers if handler.regex is None]
            nonempty_regex_handlers = [handler for handler in self._chat_handlers if handler.regex is not None]
            for handler in nonempty_regex_handlers:
                if handler.regex:
                    regex_match = re.search(handler.regex, message.text)
                    if regex_match and handler.matches_context_states(context):
                        matching_handlers.append(handler)
            if not matching_handlers:
                for handler in empty_regex_handlers:
                    if handler.matches_context_states(context):
                        matching_handlers.append(handler)
            # Run all handlers in order
            matching_handlers.sort(lambda handler: handler.order)
            for handler in matching_handlers:
                try:
                    handler.handle(context)
                except Exception as e:
                    self.logger.exception(f"Failed to run handler for {context.message}")

    def register_handlers(self):
        self.register_handler("^(u|unsubscribe)$", self.unsubscribe_handler)
        self.register_handler("", handle_greet_customer, chat_session_states={MobotChatSession.State.NOT_GREETED}, order=1) # First, say hello to the customer
        self.register_handler("", handle_start_conversation, chat_session_states={MobotChatSession.State.NOT_GREETED}, order=2) # Then, handle setting up drop session
        self.register_handler("", handle_already_greeted, chat_session_states={MobotChatSession.State.INTRODUCTION_GIVEN})
        self.register_handler("^p$", privacy_policy_handler)
        self.register_handler("^(i|inventory)$", inventory_handler, drop_session_states={DropSession.State.ACCEPTED, DropSession.State.CREATED, DropSession.State.OFFERED})

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
