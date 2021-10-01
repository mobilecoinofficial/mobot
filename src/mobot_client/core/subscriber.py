# Copyright (c) 2021 MobileCoin. All rights reserved.

import logging
import re
import sys
import threading
import time
import signal
from halo import Halo
from typing import Callable, Iterator
from concurrent.futures import as_completed, ThreadPoolExecutor, Future

import mc_util
import mobilecoin as mc
import pytz
from django.utils import timezone
from django.db import connection
from django.conf import settings

from mobot_client.air_drop_session import AirDropSession
from mobot_client.chat_strings import ChatStrings
from mobot_client.core import ConfigurationException
from mobot_client.drop_session import BaseDropSession
from mobot_client.item_drop_session import ItemDropSession
from mobot_client.logger import SignalMessenger
from mobot_client.models import Store, SessionState, DropType, Drop, BonusCoin, Sku, Order, OrderStatus, \
    CustomerStorePreferences, DropSession
from mobot_client.models.messages import Message, MessageStatus, MobotResponse
from mobot_client.payments import MCClient, Payments
from mobot_client.core.context import ChatContext


class MOBotSubscriber:
    """
    MOBot is the container which holds all of the business logic relevant to a Drop.
    """

    def __init__(self, store: Store, messenger: SignalMessenger, mcc: MCClient, payments: Payments):
        self._run = True
        self._chat_handlers = []
        self._payment_handlers = []
        self.store: Store = store
        if not self.store:
            raise ConfigurationException("No store found!")
        self.logger = logging.getLogger(f"MOBot({self.store})")
        self.messenger = messenger

        self.mcc = mcc
        self.public_address = mcc.public_address
        self.minimum_fee_pmob = mcc.minimum_fee_pmob
        self._listener_thread = None
        self._thread_count = 0
        self._number_processed = 0
        self._thread_lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=4)
        self.payments = payments
        self._futures = {}

        # self.timeouts = Timeouts(self.messenger, self.payments, schedule=30, idle_timeout=60, cancel_timeout=300)

        self.register_payment_handler(self.handle_payment)
        self.register_chat_handler("\+", self.chat_router_plus)
        self.register_chat_handler("coins", self.chat_router_coins)
        self.register_chat_handler("items", self.chat_router_items)
        self.register_chat_handler("unsubscribe", self.unsubscribe_handler)
        self.register_chat_handler("subscribe", self.subscribe_handler)
        self.register_chat_handler("health", self.health_handler)
        self.register_chat_handler("", self.default_handler)

    def _isolated_handler(self, func):
        def isolated(*args, **kwargs):
            try:
                func(*args, **kwargs)
            except Exception as e:
                self.logger.exception(f"Chat exception while processing: --- {func.__name__}({args}, {kwargs})\n")
        return isolated

    def register_chat_handler(self, regex, func, order=100):
        self.logger.info(f"Registering chat handler for {regex if regex else 'default'}")
        regex = re.compile(regex, re.I)

        self._chat_handlers.append((order, regex, self._isolated_handler(func)))
        # Use only the first value to sort so that declaration order doesn't change.
        self._chat_handlers.sort(key=lambda x: x[0])

    def register_payment_handler(self, func):
        isolated = self._isolated_handler(func)
        self._payment_handlers.append(isolated)
        return isolated

    def maybe_advertise_drop(self, message: Message):
        customer = message.customer
        self.logger.info("Checking for advertising drop")
        drop_to_advertise = BaseDropSession.get_advertising_drop()
        if drop_to_advertise is not None:
            if not customer.matches_country_code_restriction(drop_to_advertise):
                self.messenger.log_and_send_message(
                    ChatStrings.COUNTRY_RESTRICTED
                )
            else:
                bst_time = drop_to_advertise.start_time.astimezone(
                    pytz.timezone(drop_to_advertise.timezone)
                )
                response_message = ChatStrings.STORE_CLOSED.format(
                    date=bst_time.strftime("%A, %b %d"),
                    time=bst_time.strftime("%-I:%M %p %Z"),
                    desc=drop_to_advertise.pre_drop_description
                )
                self.messenger.log_and_send_message(
                    response_message
                )
                return True
        else:
            return False

    def handle_unsolicited_payment(self, message: Message):
        customer = message.customer
        amount_paid_mob = mc.pmob2mob(message.payment.amount_mob)
        self.logger.warning("Could not find drop session for customer; Payment unsolicited!")
        if mc.pmob2mob(self.minimum_fee_pmob) < amount_paid_mob:
            self.messenger.log_and_send_message(
                ChatStrings.UNSOLICITED_PAYMENT
            )
            self.payments.send_reply_payment(amount_paid_mob, False, memo="Unsolicited payment refund")
        else:
            self.messenger.log_and_send_message(
                ChatStrings.UNSOLICITED_NOT_ENOUGH
            )

    def handle_payment(self, ctx: ChatContext):
        message = ctx.message
        payment = message.payment
        message.refresh_from_db()
        source = str(message.customer.phone_number)
        self.logger.info(f"Received payment from {source}")
        self.logger.info(f"Received payment {payment}")
        receipt_status = None
        transaction_status = "TransactionPending"

        if isinstance(source, dict):
            source = source["number"]

        self.logger.info(f"received receipt {payment.signal_payment.receipt}")
        receipt = mc_util.b64_receipt_to_full_service_receipt(payment.signal_payment.receipt)

        while transaction_status == "TransactionPending":
            receipt_status = self.mcc.check_receiver_receipt_status(
                self.mcc.public_address, receipt
            )
            transaction_status = receipt_status["receipt_transaction_status"]
            self.logger.info(f"Waiting for {receipt}, current status {receipt_status}")

        if transaction_status != "TransactionSuccess":
            self.logger.error(f"failed {transaction_status}")
            return "The transaction failed!"

        amount_paid_mob = mc.pmob2mob(receipt_status["txo"]["value_pmob"])
        customer = payment.message.customer
        drop_session = customer.drop_sessions.filter(state=SessionState.WAITING_FOR_PAYMENT).first()

        if drop_session:
            self.logger.info(f"Found drop session {drop_session} awaiting payment")
            if drop_session.drop.drop_type == DropType.AIRDROP:
                air_drop = AirDropSession(self.store, self.payments, self.messenger)
                air_drop.handle_airdrop_payment(
                    source, customer, amount_paid_mob, drop_session
                )
            elif drop_session.drop.drop_type == DropType.ITEM:
                item_drop = ItemDropSession(self.store, self.payments, self.messenger)
                item_drop.handle_item_payment(
                    amount_paid_mob, drop_session
                )
        else:
            self.handle_unsolicited_payment(payment.message)

    def chat_router_plus(self, _: ChatContext):
        message_to_send = ChatStrings.PLUS_SIGN_HELP
        message_to_send += f"\n{ChatStrings.PAY_HELP}"
        self.messenger.log_and_send_message(message_to_send)

    def health_handler(self, _: ChatContext):
        self.messenger.log_and_send_message("Ok!")

    def chat_router_coins(self, ctx: ChatContext):
        active_drop = Drop.objects.get_active_drop()
        if not active_drop:
            return "No active drop to check on coins"
        else:
            bonus_coins = BonusCoin.objects.filter(drop=active_drop)
            message_to_send = ChatStrings.COINS_SENT.format(
                initial_num_sent=active_drop.num_initial_sent(),
                total=active_drop.initial_mob_disbursed(),
            )
            for bonus_coin in bonus_coins:
                message_to_send += (
                    f"\n{bonus_coin.number_claimed} / {bonus_coin.number_available_at_start} - {bonus_coin.amount_mob.normalize()} claimed"
                )
            self.messenger.log_and_send_message(message_to_send)

    def chat_router_items(self, ctx: ChatContext):
        active_drop = Drop.objects.get_active_drop()
        if active_drop is None:
            return "No active drop to check on items"

        skus = Sku.objects.filter(item=active_drop.item).order_by("sort_order")
        message_to_send = ""
        for sku in skus:
            number_ordered = Order.objects.filter(sku=sku).exclude(status=OrderStatus.CANCELLED).count()
            message_to_send += (
                f"{sku.identifier} - {number_ordered} / {sku.quantity} ordered\n"
            )
        return message_to_send

    def unsubscribe_handler(self, ctx: ChatContext):
        customer = ctx.customer
        store_preferences = customer.store_preferences(self.store)
        if store_preferences:
            if not store_preferences.allows_contact:
                self.messenger.log_and_send_message(ChatStrings.NOTIFICATIONS_OFF)
        else:
            store_preferences = CustomerStorePreferences.objects.create(
                customer=customer, store=self.store
            )

        store_preferences = customer.store_preferences(store=self.store)
        store_preferences.allows_contact = False
        store_preferences.save()

        self.messenger.log_and_send_message(ChatStrings.DISABLE_NOTIFICATIONS)

    def subscribe_handler(self, ctx: ChatContext):
        customer = ctx.customer
        store_preferences, _is_new = CustomerStorePreferences.objects.get_or_create(
            customer=customer, store=self.store
        )

        if store_preferences.allows_contact:
            self.messenger.log_and_send_message(ChatStrings.ALREADY_SUBSCRIBED)
        else:
            store_preferences.allows_contact = True
            store_preferences.save()
            self.messenger.log_and_send_message(ChatStrings.SUBSCRIBE_NOTIFICATIONS)

    def handle_new_drop_session(self, active_drop: Drop):
        ctx = ChatContext.get_current_context()
        customer, message = (ctx.customer, ctx.message)
        if active_drop.drop_type == DropType.AIRDROP:
        # if this is an airdrop session, dispatch to the
        # no_active_airdrop session handler to initiate a session
            air_drop = AirDropSession(self.store, self.payments, self.messenger)
            air_drop.handle_no_active_airdrop_drop_session(
                customer, message, active_drop
            )
        elif active_drop.drop_type == DropType.ITEM:
            # if this is an item drop session, dispacth to the
            # no_active_item_drop session handler to initiate a session
            item_drop = ItemDropSession(self.store, self.payments, self.messenger)
            item_drop.handle_no_active_item_drop_session(
                customer, message, active_drop
            )
        else:
            raise Exception("Unknown Drop Type")

    def default_handler(self, ctx: ChatContext):
        self.logger.info(f"NOW ROUTING CHAT {ctx.message}")
        message = ctx.message
        # Store the message
        customer = ctx.customer

        # see if there is an active airdrop session
        active_drop_session: DropSession = customer.active_drop_sessions().first()

        if not active_drop_session:
            self.logger.info(f"Found no active session for customer {customer}")
            self.logger.info(f"Searching for active drops...")
            active_drop = Drop.objects.get_active_drop()
            if active_drop:
                self.logger.info(f"Active drop found: {active_drop}")
                self.handle_new_drop_session(active_drop)
            else:
                self.logger.warning(f"No active drops; Sending Store Closed message to customer {customer}")
                if not self.maybe_advertise_drop(message):
                    self.messenger.log_and_send_message(ChatStrings.STORE_CLOSED_SHORT)
        else:
            self.logger.info(f"Found a drop session for customer {customer} of type {active_drop_session.drop.drop_type}")
            if not active_drop_session.manual_override:
                # manual_override means that a human is monitoring the chat via a linked
                # device and wants to respond rather than having MOBot respond, so do
                # nothing.
                if active_drop_session.drop.drop_type == DropType.AIRDROP:
                    self.logger.info(f"found active air drop session in state {active_drop_session.state}")
                    air_drop = AirDropSession(self.store, self.payments, self.messenger)
                    air_drop.handle_active_airdrop_drop_session(
                        message, active_drop_session
                    )
                elif active_drop_session.drop.drop_type == DropType.ITEM:
                    # there *is* an active item drop session.
                    self.logger.info(f"found active item drop session in state {active_drop_session.state}")
                    # dispatch to active_item_drop session handler
                    item_drop = ItemDropSession(self.store, self.payments, self.messenger)
                    item_drop.handle_active_item_drop_session(message, active_drop_session)
                else:
                    raise Exception("Unknown drop type")

    def _find_handler(self, message: Message) -> Callable:
        """Perform a regex match search to find an appropriate handler for an incoming message"""
        self.logger.info(f"Finding handler for message {message}")
        if message.text is None:
            return self.handle_payment
        else:
            filtered = list(filter(lambda handler: re.search(handler[1], message.text), self._chat_handlers))[0]
            _, _, func = filtered
            return func

    def acknowledge_message(self, message: Message):
        if message.payment is not None:
            self.logger.info("Customer sent payment; acknowledging immediately")
            self.messenger.log_and_send_message(ChatStrings.PAYMENT_RECEIVED)
        if Message.objects.queue_size >= settings.CONCURRENCY_WARNING_MESSAGE_THRESHOLD:
            self.logger.info(f"Queue threshold {Message.objects.queue_size} above {settings.CONCURRENCY_WARNING_MESSAGE_THRESHOLD}")
            self.messenger.log_and_send_message(ChatStrings.MOBOT_HEAVY_LOAD)

    def process_message(self, message: Message) -> Message:
        """Enter a chat context to manage which message/payment we're currently replying to
            :param: message: Message to process

            :return: The processed message
            :rtype: Message
        """
        with ChatContext(message) as ctx:
            try:
                self.acknowledge_message(message)
                self.logger.exception("Got exception acking")
                handler = self._find_handler(message)
                result = handler(ctx)
                return message
            except Exception as e:
                self.logger.exception("Processing message failed!")
                raise e

    @Halo(text='Waiting for next message...', spinner='dots')
    def _get_next_message(self) -> Message:
        """
        Get a message off the DB, show a spinner while waiting

        :return: The next available message to process
        :rtype: Message
        """
        while self._run:
            try:
                message = Message.objects.get_message(self.store)
                if message:
                    return message
                else:
                    time.sleep(1)
            except Exception as e:
                self.logger.exception("Exception getting message!")
                raise e

    def _get_and_process(self, pool: ThreadPoolExecutor) -> Future[Message]:
        try:
            message: Message = self._get_next_message()
            self.logger.info("Got message!")
            process_fut = pool.submit(self.process_message, message)
            self._futures[message.pk] = process_fut
            return process_fut
        except Exception as e:
            self.logger.exception(f"Exception processing messages.")

    def stop_chat(self):
        self._run = False
        try:
            for future in as_completed(self._futures.values()):
                future.result()
        except Exception:
            self.logger.exception("Error stopping chat")

        self.logger.warning("Stopping message processing!")

    def _done(self, fut: Future[Message]):
        """
        Clean up future list
        :param fut: The message future
        :return: None
        """
        try:
            result = fut.result()
            del self._futures[result.pk]
        except TimeoutError as e:
            self.logger.exception("Message processing timed out.")
        except Exception as e:
            self.logger.exception("Error cleaning up future")

    def run_chat(self, process_max: int = 0) -> int:
        """Start looking for messages off DB and process.
                :argument process_max: Number of messages to process before stopping, if > 0
        """
        self.logger.info("Now running MOBot chat...")
        with self._pool as pool:
            while self._run:
                processed = self._get_and_process(pool)
                processed.add_done_callback(self._done)
                self._number_processed += 1
                if process_max > 0 and self._number_processed == process_max:
                    self.stop_chat()
            self.stop_chat()

