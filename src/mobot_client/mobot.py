# Copyright (c) 2021 MobileCoin. All rights reserved.


import os
import mobilecoin as mc
import pytz
import logging
from decimal import Decimal

from django.utils import timezone
from django.conf import settings

from mobot_client.payments.client import MCClient
from signald_client import Signal

from mobot_client.logger import SignalMessenger
from mobot_client.models import (
    Customer,
    DropSession,
    Drop,
    CustomerStorePreferences,
    BonusCoin,
    Order,
    Sku, SessionState, DropType, OrderStatus, Store,
)
from mobot_client.drop_session import (
    BaseDropSession,
)
from mobot_client.air_drop_session import AirDropSession
from mobot_client.item_drop_session import ItemDropSession
from mobot_client.payments import Payments
from mobot_client.chat_strings import ChatStrings
from mobot_client.timeouts import Timeouts
from mobot_client.utils import TimerFactory


class ConfigurationException(Exception):
    pass


class MOBot:
    """
    MOBot is the container which holds all of the business logic relevant to a Drop.
    """
    def __init__(self, bot_name: str, bot_avatar_filename: str, store: Store, signal: Signal, mcc: MCClient):
        self.store: Store = store
        if not self.store:
            raise ConfigurationException("No store found!")
        self.logger = logging.getLogger("MOBot")
        self.timers = TimerFactory("MOBot", self.logger)
        self.signal = signal
        self.messenger = SignalMessenger(self.signal, self.store)

        self.mcc = mcc
        self.public_address = mcc.public_address
        self.minimum_fee_pmob = mcc.minimum_fee_pmob

        self.payments = Payments(
            mobilecoin_client=self.mcc,
            store=self.store,
            messenger=self.messenger,
            signal=signal
        )

        # self.timeouts = Timeouts(self.messenger, self.payments, schedule=30, idle_timeout=60, cancel_timeout=300)

        self.logger.info(f"bot_avatar_filename {bot_avatar_filename}")
        b64_public_address = mc.utility.b58_wrapper_to_b64_public_address(
            self.mcc.public_address
        )

        resp = self.signal.set_profile(
            bot_name, b64_public_address, bot_avatar_filename, True
        )
        self.logger.info("set profile response", resp)
        if resp.get("error"):
            assert False, resp

        with self.timers.get_timer("Register_handlers"):
            self.signal.register_payment_handler(self.handle_payment)
            self.signal.register_handler("\+", self.chat_router_plus)
            self.signal.register_handler("coins", self.chat_router_coins)
            self.signal.register_handler("items", self.chat_router_items)
            self.signal.register_handler("unsubscribe", self.unsubscribe_handler)
            self.signal.register_handler("subscribe", self.subscribe_handler)
            self.signal.register_handler("", self.default_handler)

    def maybe_advertise_drop(self, customer):
        self.logger.info("Checking for advertising drop")
        drop_to_advertise = BaseDropSession.get_advertising_drop()
        if drop_to_advertise is not None:
            if not customer.matches_country_code_restriction(drop_to_advertise):
                self.messenger.log_and_send_message(
                    customer, customer.phone_number, ChatStrings.COUNTRY_RESTRICTED
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
                    customer, customer.phone_number, response_message
                )
                return True
        else:
            return False

    def handle_unsolicited_payment(self, customer: Customer, amount_paid_mob: Decimal):
        self.logger.warning("Could not find drop session for customer; Payment unsolicited!")
        if mc.pmob2mob(self.minimum_fee_pmob) < amount_paid_mob:
            self.messenger.log_and_send_message(
                customer, str(customer.phone_number), ChatStrings.UNSOLICITED_PAYMENT
            )
            self.payments.send_mob_to_customer(customer, str(customer.phone_number.as_e164), amount_paid_mob, False)
        else:
            self.messenger.log_and_send_message(
                customer, str(customer.phone_number), ChatStrings.UNSOLICITED_NOT_ENOUGH
            )

    def handle_payment(self, source, receipt):
        with self.timers.get_timer("handle_payment"):
            self.logger.info(f"Received payment from {source}")
            receipt_status = None
            transaction_status = "TransactionPending"

            if isinstance(source, dict):
                source = source["number"]

            self.logger.info(f"received receipt {receipt}")
            receipt = mc.utility.b64_receipt_to_full_service_receipt(receipt.receipt)

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
            customer, _ = Customer.objects.get_or_create(phone_number=source)
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
                self.handle_unsolicited_payment(customer, amount_paid_mob)

    def chat_router_plus(self, message, match):
        self.logger.debug(message)
        customer, _ = Customer.objects.get_or_create(phone_number=message.source['number'])
        message_to_send = ChatStrings.PLUS_SIGN_HELP
        message_to_send += f"\n{ChatStrings.PAY_HELP}"
        self.messenger.log_and_send_message(customer, customer.phone_number, message_to_send)

    def chat_router_coins(self, message, match):
        customer, _ = Customer.objects.get_or_create(phone_number=message.source['number'])
        active_drop = Drop.objects.get_active_drop()
        if not active_drop:
            return "No active drop to check on coins"
        else:
            bonus_coins = BonusCoin.objects.filter(drop=active_drop)
            message_to_send = ChatStrings.COINS_SENT.format(
                initial_num_sent=active_drop.num_initial_sent(),
                total=mc.utility.pmob2mob(active_drop.initial_pmob_disbursed()),
            )
            for bonus_coin in bonus_coins:
                message_to_send += (
                    f"\n{bonus_coin.number_claimed()} / {bonus_coin.number_available_at_start} - {mc.pmob2mob(bonus_coin.amount_pmob).normalize()} claimed"
                )
            self.messenger.log_and_send_message(customer, customer.phone_number, message_to_send)

    def chat_router_items(self, message, match):
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

    def unsubscribe_handler(self, message, _match):
        customer, _is_new = Customer.objects.get_or_create(
            phone_number=message.source["number"]
        )
        store_preferences = customer.store_preferences(self.store)
        if store_preferences:
            if not store_preferences.allows_contact:
                self.messenger.log_and_send_message(
                    customer, message.source, ChatStrings.NOTIFICATIONS_OFF
                )
        else:
            store_preferences = CustomerStorePreferences.objects.create(
                customer=customer, store=self.store
            )

        store_preferences = customer.store_preferences(store=self.store)
        store_preferences.allows_contact = False
        store_preferences.save()

        self.messenger.log_and_send_message(
            customer, message.source, ChatStrings.DISABLE_NOTIFICATIONS
        )

    def subscribe_handler(self, message, _match):
        customer, _is_new = Customer.objects.get_or_create(
            phone_number=message.source["number"]
        )
        store_preferences, _is_new = CustomerStorePreferences.objects.get_or_create(
            customer=customer, store=self.store
        )

        if store_preferences.allows_contact:
            self.messenger.log_and_send_message(
                customer, message.source, ChatStrings.ALREADY_SUBSCRIBED
            )
            return

        store_preferences.allows_contact = True
        store_preferences.save()

        self.messenger.log_and_send_message(
            customer, message.source, ChatStrings.SUBSCRIBE_NOTIFICATIONS
        )

    def handle_new_drop_session(self, customer: Customer, message, active_drop: Drop):
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

    def default_handler(self, message, match):
        # Store the message
        self.logger.info(f"\033[1;33m NOW ROUTING CHAT\033[0m {message}")
        customer, _ = Customer.objects.get_or_create(
            phone_number=message.source["number"]
        )
        
        self.messenger.log_received(message, customer, self.store)
        # see if there is an active airdrop session
        active_drop_session: DropSession = customer.active_drop_sessions().first()

        if not active_drop_session:
            self.logger.info(f"Found no active session for customer {customer}")
            self.logger.info(f"Searching for active drops...")
            active_drop = Drop.objects.get_active_drop()
            if active_drop:
                self.logger.info(f"Active drop found: {active_drop}")
                self.handle_new_drop_session(customer, message, active_drop)
            else:
                self.logger.warning(f"No active drops; Sending Store Closed message to customer {customer}")
                if not self.maybe_advertise_drop(customer):
                    self.messenger.log_and_send_message(
                        customer, message.source, ChatStrings.STORE_CLOSED_SHORT
                    )
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


    def run_chat(self):
        # self.logger.info("Starting timeouts thread")
        # t = threading.Thread(target=self.timeouts.process_timeouts, args=(), kwargs={})
        # t.setDaemon(True)
        # t.start()

        self.logger.info("Now running MOBot chat")
        self.signal.run_chat(True)
