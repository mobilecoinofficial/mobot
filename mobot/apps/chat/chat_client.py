import re
import logging
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any, Optional
from typing import Set

import mobilecoin

from django.conf import settings
from django.utils import timezone

from .models import MobotBot, MobotChatSession
from mobot.apps.merchant_services.models import Customer, CustomerStorePreferences, DropSession, Campaign, Store
from mobot.signald_client import Signal
from mobot.lib.signal import SignalCustomerDataClient
from mobot.signald_client.types import Message as SignalMessage
from mobot.signald_client.main import QueueSubscriber
from mobot.apps.chat.context import MessageContextFactory, MessageContextBase
from .handlers import *


class TransactionStatus(str, Enum):
    TRANSACTION_SUCCESS = "TransactionSuccess"
    TRANSACTION_PENDING = "TransactionPending"


class MobotMessage(str, Enum):
    YES = "y"
    NO = "n"
    CANCEL = "cancel"
    UNSUBSCRIBE = "unsubscribe"


class MobotHandler:
    def __init__(self,
                 method: Callable[[MessageContextBase], Any],
                 context_filter: Callable[[MessageContextBase], bool] = None,
                 order: int = 100,
                 drop_session_states: Set[DropSession.State] = set(),
                 chat_session_states: Set[MobotChatSession.State] = set(),
                 ):
        self._method = method
        self.drop_session_states = drop_session_states
        self.chat_session_states = chat_session_states
        self.order = order
        self._should_run = context_filter if context_filter else lambda c: True  # If no filter, always run

    @property
    def all_states(self):
        return not self.drop_session_states and not self.chat_session_states  # empty states

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
        if self._should_run(context):
            return self._method(context)


class Mobot:
    def __init__(self, signal: Signal, mobilecoin_client: mobilecoin.Client, store: Store, campaign: Campaign):
        self.name = f"Mobot-{store.name}"
        self.logger = logging.getLogger(f"Mobot-{store.id}")
        self.signal = signal
        self.campaign = campaign
        self.store = store
        self.mobilecoin_client = mobilecoin_client
        self.mobot: MobotBot = self.get_mobot_bot()
        self.message_context_factory = MessageContextFactory(self.mobot, self.logger, self.signal)
        self.customer_data_client = SignalCustomerDataClient(signal=self.signal)
        self._subscriber = QueueSubscriber(self.name)
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
        bot, _ = MobotBot.objects.get_or_create(name=f"{self.store.name}-Bot", store=self.store, campaign=self.campaign)
        return bot

    def _regex_to_filter_func(self, regex: str) -> Callable[[MessageContextBase], bool]:
        compiled_regex = re.compile(regex)

        def matches(ctx: MessageContextBase):
            return re.search(compiled_regex, ctx.message.text)

        return matches

    def register_handler(self,
                         method: Callable[[MessageContextBase], Any],
                         condition: Optional[Callable[[MessageContextBase], bool]] = None,
                         order: int = 100,
                         chat_session_states: Set[MobotChatSession.State] = set(),
                         drop_session_states: Set[DropSession.State] = set(),
                         always_run: bool = False,
                         ):
        """

        Args:
            condition:
            regex: A regex to match message text. Leave blank to match all messages.
            method: A method that accepts a MessageContext object
            order: What order to run matched handlers in; defaults to 100. Lower numbers run first.
            chat_session_states: What ChatSession.State states this should run under
            drop_session_states: What DropSession.State states this should run under
            always_run: Normally, handlers with no regex match won't run if there are more specific matches. This sets a
                bit to always run
        """

        handler = MobotHandler(regex, method, order=order, chat_session_states=chat_session_states,
                               drop_session_states=drop_session_states, always_run=always_run)

    def set_customer_preferences(self, customer: Customer, allow_contact: bool) -> CustomerStorePreferences:
        customer_prefs = CustomerStorePreferences.objects.get_or_create(customer=customer, store=self.store)
        customer_prefs.allows_contact = allow_contact
        customer_prefs.save()
        return customer_prefs

    def find_active_campaigns(self):
        Campaign.objects.filter(start_time__gte=timezone.now(), end_time__lte=timezone.now())

    def _handle_chat(self, message: SignalMessage):
        # TODO: Would be great to cache these after they're hit... One day.
        self.logger.debug(f"Attempting to match message: {message.text}")
        context = self.get_context_from_message(message)
        with context:
            matching_handlers = []
            for handler in self._nonempty_regex_chat_handlers:
                if handler.regex:
                    regex_match = re.search(handler.regex, message.text)
                    if regex_match and handler.matches_context_states(context):
                        matching_handlers.append(handler)
            if not matching_handlers:
                for handler in self._empty_regex_chat_handlers:
                    if handler.matches_context_states(context):
                        matching_handlers.append(handler)
            # Run all handlers in order
            matching_handlers.sort(key=lambda matched_handler: matched_handler.order)
            for handler in matching_handlers:

                try:
                    self.logger.debug(f"Attempting to handle {context.message}")
                    handler.handle(context)
                except Exception:
                    self.logger.exception(f"Failed to run handler for {context.message}")

    def register_handlers(self):
        self.register_handler("^(u|unsubscribe)$", unsubscribe_handler)
        self.register_handler("^(s|subscribe)$", subscribe_handler)
        self.register_handler("", handle_greet_customer, chat_session_states={MobotChatSession.State.NOT_GREETED},
                              order=1)  # First, say hello to the customer
        self.register_handler("", handle_start_conversation, chat_session_states={MobotChatSession.State.NOT_GREETED},
                              order=2)  # Then, handle setting up drop session
        self.register_handler("", handle_already_greeted,
                              chat_session_states={MobotChatSession.State.INTRODUCTION_GIVEN})
        self.register_handler("", handle_drop_expired, drop_session_states={DropSession.State.EXPIRED})
        self.register_handler("", handle_drop_not_ready, drop_session_states={DropSession.State.NOT_READY})
        self.register_handler("", handle_no_handler_found)
        self.register_handler("^p$", privacy_policy_handler)
        self.register_handler("^(i|inventory)$", inventory_handler,
                              drop_session_states={DropSession.State.ACCEPTED, DropSession.State.OFFERED})

    def find_and_greet_targets(self, campaign):
        for customer in self.campaign.get_target_customers():
            preferences, created = CustomerStorePreferences.objects.get_or_create(customer=customer,
                                                                                  store_ref=campaign.store)

            self.logger.info("Reaching out to existing customers if they pass target validation")
            ctx = self.get_context_from_customer(customer)
            if ctx.drop_session.state == DropSession.State.CREATED:
                ctx.log_and_send_message(ChatStrings.GREETING.format(store=self.store,
                                                                     campaign=campaign,
                                                                     campaign_description=campaign.description))

    def run(self, max_messages=0):
        self.signal.register_subscriber(self._subscriber)
        with ThreadPoolExecutor(4) as executor:
            self._executor_futures.append(executor.submit(self.signal.run_chat, True))
            while True:
                for message in self._subscriber.receive_messages():
                    self.logger.debug(f"Mobot received message: {message}")
                    self._executor_futures.append(executor.submit(self.find_and_greet_targets, self.campaign))
                    # Handle in foreground while I'm testing
                    if settings.TEST:
                        self._handle_chat(message)
                    else:
                        self._executor_futures.append(executor.submit(self._handle_chat, message))
                    if max_messages:
                        if self._subscriber.total_received == max_messages:
                            executor.shutdown(wait=True)
                            return
            executor.shutdown(wait=True)
