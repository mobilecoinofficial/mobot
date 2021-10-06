# Copyright (c) 2021 MobileCoin. All rights reserved.
import mobilecoin as mc
import pytz

from mobot_client.core.context import ChatContext
from mobot_client.core.subscriber import Subscriber
from mobot_client.models.messages import Message
import mc_util

from mobot_client.logger import SignalMessenger
from mobot_client.models import (
    DropSession,
    Drop,
    CustomerStorePreferences,
    BonusCoin,
    Order,
    Sku, SessionState, DropType, OrderStatus, Store, Customer,
)
from mobot_client.drop_session import (
    BaseDropSession,
)
from mobot_client.air_drop_session import AirDropSession
from mobot_client.item_drop_session import ItemDropSession
from mobot_client.chat_strings import ChatStrings
from mobot_client.payments import Payments

import os
import django


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mobot.settings")
django.setup()


class ConfigurationException(Exception):
    pass


class DropRunner(Subscriber):
    """
    MOBot is the container which holds all of the business logic relevant to a Drop.
    """
    def __init__(self, store: Store, messenger: SignalMessenger, payments: Payments):
        super().__init__(store, messenger)
        self.payments = payments
        self.logger.info("Registering handlers...")
        self.register_payment_handler(self.handle_payment)
        self.register_chat_handler("\+", self.chat_router_plus)
        self.register_chat_handler("coins", self.chat_router_coins)
        # TODO: Split up items/event runner vs. Airdrop runner?
        self.register_chat_handler("items", self.chat_router_items)
        self.register_chat_handler("unsubscribe", self.unsubscribe_handler)
        self.register_chat_handler("subscribe", self.subscribe_handler)
        self.register_chat_handler("health", self.health_handler)
        self.register_chat_handler("", self.default_handler)

    def maybe_advertise_drop(self, customer: Customer):
        """Figure out whether or not there's a drop running, and send a message if it is"""
        self.logger.info("Checking for advertising drop")
        drop_to_advertise = BaseDropSession.get_advertising_drop()
        if drop_to_advertise is not None:
            if not customer.matches_country_code_restriction(drop_to_advertise):
                self.messenger.log_and_send_message(
                    ChatStrings.COUNTRY_RESTRICTED
                )
                return True
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
        amount_paid_mob = message.payment.amount_mob
        self.logger.warning("Could not find drop session for customer; Payment unsolicited!")
        minimum_fee_mob = self.payments.minimum_fee_mob

        if minimum_fee_mob < amount_paid_mob:
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
            receipt_status = self.payments.mcc.check_receiver_receipt_status(
                self.payments.mcc.public_address, receipt
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
        """A health check chat router; in the future:
           - Should ensure connection to DB
           - Should ensure connection to Signal
           - Should esnure connection to Full-Service
        """
        self.messenger.log_and_send_message("Ok!")

    def chat_router_coins(self, _: ChatContext):
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

    def chat_router_items(self, _: ChatContext):
        active_drop = Drop.objects.get_active_drop()
        if active_drop is None:
            message_to_send = "No active drop to check on Items"
        else:
            skus = Sku.objects.filter(item=active_drop.item).order_by("sort_order")
            message_to_send = ""
            for sku in skus:
                number_ordered = Order.objects.filter(sku=sku).exclude(status=OrderStatus.CANCELLED).count()
                message_to_send += (
                    f"{sku.identifier} - {number_ordered} / {sku.quantity} ordered\n"
                )
        self.messenger.log_and_send_message(message_to_send)

    def unsubscribe_handler(self, ctx: ChatContext):
        customer = ctx.customer
        store_preferences = customer.store_preferences(self.store)
        if store_preferences:
            if not store_preferences.allows_contact:
                self.messenger.log_and_send_message(ChatStrings.NOTIFICATIONS_OFF)
        else:
            CustomerStorePreferences.objects.create(
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
        if active_drop.drop_type == DropType.AIRDROP:
        # if this is an airdrop session, dispatch to the
        # no_active_airdrop session handler to initiate a session
            air_drop = AirDropSession(self.store, self.payments, self.messenger)
            air_drop.handle_no_active_airdrop_drop_session(active_drop)
        elif active_drop.drop_type == DropType.ITEM:
            # if this is an item drop session, dispacth to the
            # no_active_item_drop session handler to initiate a session
            item_drop = ItemDropSession(self.store, self.payments, self.messenger)
            item_drop.handle_no_active_item_drop_session(
                active_drop
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
                if not self.maybe_advertise_drop(customer):
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
