import logging
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Iterable

import mobilecoin

from django.conf import settings
from django.utils import timezone

from .models import MobotBot
from mobot.apps.merchant_services.models import Customer, CustomerStorePreferences, Campaign, MobotStore, Order
from mobot.signald_client import Signal
from mobot.lib.signal import SignalCustomerDataClient
from mobot.signald_client.types import Message as SignalMessage
from mobot.signald_client.main import QueueSubscriber
from mobot.apps.chat.context import MessageContextManager
from mobot.apps.payment_service.service import PaymentService
from .handlers import *
from .utils import *


class TransactionStatus(str, Enum):
    TRANSACTION_SUCCESS = "TransactionSuccess"
    TRANSACTION_PENDING = "TransactionPending"


class MobotMessage(str, Enum):
    YES = "y"
    NO = "n"
    CANCEL = "cancel"
    UNSUBSCRIBE = "unsubscribe"


class NoMatchingHandlerException(Exception):
    pass


class MobotDispatcher:
    def __init__(self,
                 name: str,
                 method: Callable[[MobotContext], Any],
                 order: int = 100,
                 conditions: Iterable[Callable[[MobotContext], bool]] = [],
                 text_filtered: bool = False,
                 ):
        self.name = name
        self._method = method
        self.ctx_conditions = conditions
        self.order = order
        self.text_filtered = text_filtered

    def context_matches(self, context: MobotContext):
        match = all([cond(context) for cond in self.ctx_conditions]) if self.ctx_conditions else True
        return match

    def handle(self, context: MobotContext):
        return self._method(context)

    def __str__(self):
        return f"{self.name} Handler"


class Mobot:
    def __init__(self,
                 signal: Signal,
                 fullservice: mobilecoin.Client,
                 store: MobotStore,
                 campaign: Campaign):
        self.name = f"Mobot-{store.name}"
        self.logger = logging.getLogger(f"Mobot-{store.id}")
        self.signal = signal
        self.campaign = campaign
        self.store = store
        self.payment_service = PaymentService(fullservice)
        self.mobot: MobotBot = self.get_mobot_bot()
        self.message_context_manager = MessageContextManager(self.mobot, self.logger, self.signal, payment_service=self.payment_service)
        self.customer_data_client = SignalCustomerDataClient(signal=self.signal)
        self._subscriber = QueueSubscriber(self.name)
        self._executor_futures = []
        self.handlers = []
        self._executor = ThreadPoolExecutor(4)

    def get_context_from_message(self, message: SignalMessage) -> MobotContext:
        context: MobotContext = self.message_context_manager.get_message_context(message)
        return context

    def get_context_from_customer(self, customer: Customer) -> MobotContext:
        context = self.message_context_manager.get_message_context(message=None, customer=customer)
        return context

    def get_mobot_bot(self) -> MobotBot:
        bot, _ = MobotBot.objects.get_or_create(name=f"{self.store.name}-Bot", store=self.store, campaign=self.campaign)
        return bot

    def register_handler(self, name: str, method: Callable[[MobotContext], Any], regex: str = "", order: int = 100,
                         chat_session_states: Set[MobotChatSession.State] = set(),
                         drop_session_states: Set[DropSession.State] = set(),
                         ctx_conditions: List[MobotContextFilter] = []):
        """

        Args:
            name: Name of the handler, for debugging
            method: A method to take that accepts a MobotContext
            regex: Some regex to match
            order: An order to execute compared to other matching handlers
            chat_session_states: A set of drop session states for the handler to run
            drop_session_states: A set of chat session states for the handler to run
            ctx_conditions: Any lambdas that take a MobotContext and produce a boolean, for filtering
        """
        conditions = ctx_conditions.copy()
        if regex:
            conditions.append(regex_filter(regex))
        if drop_session_states:
            conditions.append(drop_session_state_filter(drop_session_states))
        if chat_session_states:
            conditions.append(chat_session_state_filter(chat_session_states))

        dispatch_handler = MobotDispatcher(
            name,
            method,
            text_filtered=True if regex else False,
            order=order,
            conditions=conditions)

        self.handlers.append(dispatch_handler)

    # TODO: Not currently in use; will be used later to serve multiple campaigns
    def find_active_campaigns(self) -> Iterable[Campaign]:
        """
        Not currently in use. Will be used in the future to get all campaigns for a store and serve all of them.
        Returns:
            Iterable[Campaign]
        """
        return Campaign.objects.filter(store=self.store, start_time__gte=timezone.now(), end_time__lte=timezone.now())

    def _handle_chat(self, message: SignalMessage):
        # TODO: Would be great to cache these after they're hit... One day.
        self.logger.debug(f"Attempting to match message: {message.text}")
        context = self.get_context_from_message(message)
        with context:
            matching_handlers = []
            for handler in self.handlers:
                # First, check for explicit text or payment
                if handler.context_matches(context) and handler.text_filtered or context.message.payment is not None:
                    print(f"\033[1;34m Appending handler {handler}!\033[0m")
                    matching_handlers.append(handler)
            if not matching_handlers:
                for handler in self.handlers:
                    if handler.context_matches(context):
                        print(f"\033[1;31m Appending handler {handler}!\033[0m")
                        matching_handlers.append(handler)
            matching_handlers.sort(key=lambda matched_handler: matched_handler.order)
            for handler in matching_handlers:
                try:
                    print(f"\033[1;35m Attempting to handle {handler}\033[0m")
                    handler.handle(context)
                    print(f"\033[1;35m Handler handled {handler}\033[0m")
                except Exception:
                    self.logger.exception(f"Failed to run handler for {handler.name}")
            if not matching_handlers:
                raise NoMatchingHandlerException(message.text)

    def check_ctx_order_contains_unwanted_payment(self, context: MobotContext) -> bool:
        if context.message.payment:
            return context.order is not None and context.order.state != Order.State.PAYMENT_REQUESTED
        return False

    def check_ctx_order_contains_payment(self, context: MobotContext) -> bool:
        return context.message.payment is not None

    def register_default_handlers(self):
        # FIXME: regex should be case agnostic
        self.register_handler(name="unsubscribe", regex="^(U|u|unsubscribe)$", method=unsubscribe_handler)
        self.register_handler(name="subscribe", regex="^(S|s|subscribe)$", method=subscribe_handler)
        self.register_handler(name="greet", method=handle_greet_customer,
                              chat_session_states={MobotChatSession.State.NOT_GREETED},
                              order=1)  # First, say hello to the customer
        self.register_handler(name="redisplay", regex="^(\?)$", method=handle_greet_customer)
        self.register_handler(name="start", method=handle_start_conversation,
                              chat_session_states={MobotChatSession.State.NOT_GREETED},
                              order=2)  # Then, handle setting up drop session
        self.register_handler(name="offer_accepted", regex="^(Y|y|yes)$", method=handle_drop_offer_accepted,
                              drop_session_states={DropSession.State.OFFERED})
        self.register_handler(name="offer_rejected", regex="^(N|n|no)$", method=handle_drop_offer_rejected,
                              drop_session_states={DropSession.State.OFFERED})
        self.register_handler(name="already greeted", method=handle_already_greeted,
                              chat_session_states={MobotChatSession.State.INTRODUCTION_GIVEN})
        self.register_handler(name="expired", method=handle_drop_expired,
                              drop_session_states={DropSession.State.EXPIRED})
        self.register_handler(name="not ready", method=handle_drop_not_ready,
                              drop_session_states={DropSession.State.NOT_READY})
        self.register_handler(name="no other handler found", method=handle_no_handler_found,
                              chat_session_states={MobotChatSession.State.INTRODUCTION_GIVEN})
        self.register_handler(name="privacy", regex="^(P|p|privacy)$", method=privacy_policy_handler)
        # FIXME: inventory handler doesn't seem to work, and I get 2 "Sorry, I didn't understand that" responses - I think the issue was area code was not allowed - should make sure the response is "You can't participate"
        self.register_handler(name="inventory", regex="^(I|i|inventory)$", method=inventory_handler) # FIXME should this have drop_session_states?
        self.register_handler(name="unsolicited_payment", method=handle_unsolicited_payment,
                              ctx_conditions=[self.check_ctx_order_contains_unwanted_payment])
        self.register_handler(name="payment", method=handle_order_payment,
                              ctx_conditions=[self.check_ctx_order_contains_payment])

    def find_and_greet_targets(self, campaign):
        for customer in self.campaign.get_target_customers():
            preferences, created = CustomerStorePreferences.objects.get_or_create(customer=customer,
                                                                                  store_ref=campaign.store)
            ctx = self.get_context_from_customer(customer)
            if ctx.drop_session.state == DropSession.State.CREATED:
                if preferences.allows_contact:
                    ctx.log_and_send_message(ChatStrings.GREETING.format(store=self.store,
                                                                         campaign=campaign,
                                                                         campaign_description=campaign.description))

    def _shutdown_now(self):
        self._executor.shutdown(wait=False)

    def _shutdown_gracefully(self):
        self._executor.shutdown(wait=True)

    def _submit_future(self, callable: Callable, *args):
        self._executor_futures.append(self._executor.submit(callable, *args))

    def run(self, max_messages=0):
        self.signal.register_subscriber(self._subscriber)
        self._submit_future(self.signal.run_chat, True)
        while True:
            for message in self._subscriber.receive_messages():
                self.logger.debug(f"Mobot received message: {message}")
                self._submit_future(self.find_and_greet_targets, self.campaign)
                # Handle in foreground while I'm testing
                if settings.TEST:
                    self._handle_chat(message)
                else:
                    self._submit_future(self._handle_chat, message)
                if max_messages:
                    if self._subscriber.total_received == max_messages:
                        self._shutdown_gracefully()
                        return
            self._executor.shutdown(wait=True)


