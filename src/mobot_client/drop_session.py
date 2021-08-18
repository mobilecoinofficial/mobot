# Copyright (c) 2021 MobileCoin. All rights reserved.

import enum
import mobilecoin as mc

from decimal import Decimal
from django.utils import timezone
from mobot_client.models import DropSession, Drop, CustomerStorePreferences, Order, Sku
from mobot_client.chat_strings import ChatStrings


class SessionStateReadyToReceiveInitial(enum.Enum):
    NOT_READY = 0
    READY = 1


class SessionState(enum.Enum):
    OUT_OF_MOB = -2
    CANCELLED = -1
    READY_TO_RECEIVE_INITIAL = 0
    WAITING_FOR_BONUS_TRANSACTION = 1
    ALLOW_CONTACT_REQUESTED = 2
    COMPLETED = 3


class ItemSessionState(enum.Enum):
    IDLE_AND_REFUNDABLE = -4
    IDLE = -3
    REFUNDED = -2
    CANCELLED = -1
    NEW = 0
    WAITING_FOR_PAYMENT = 1
    WAITING_FOR_SIZE = 2
    WAITING_FOR_NAME = 3
    WAITING_FOR_ADDRESS = 4
    SHIPPING_INFO_CONFIRMATION = 5
    ALLOW_CONTACT_REQUESTED = 6
    COMPLETED = 7

    @classmethod
    def active_states(cls):
        return {
                cls.NEW.value,
                cls.WAITING_FOR_PAYMENT.value,
                cls.WAITING_FOR_SIZE.value,
                cls.WAITING_FOR_NAME.value,
                cls.WAITING_FOR_ADDRESS.value,
                cls.SHIPPING_INFO_CONFIRMATION.value,
                cls.ALLOW_CONTACT_REQUESTED.value
            }

    @classmethod
    def refundable_states(cls):
        return {
            cls.IDLE_AND_REFUNDABLE.value,
            cls.WAITING_FOR_SIZE.value,
            cls.WAITING_FOR_ADDRESS.value,
            cls.WAITING_FOR_ADDRESS.value,
            cls.WAITING_FOR_NAME.value,
            cls.SHIPPING_INFO_CONFIRMATION.value,
        }


class DropType(enum.Enum):
    AIRDROP = 0
    ITEM = 1


class BaseDropSession:
    def __init__(self, store, payments, messenger):
        self.store = store
        self.payments = payments
        self.messenger = messenger

    @staticmethod
    def get_advertising_drop():
        drops_to_advertise = Drop.objects.filter(
            advertisment_start_time__lte=timezone.now()
        ).filter(start_time__gt=timezone.now())

        if len(drops_to_advertise) > 0:
            return drops_to_advertise[0]
        return None

    @staticmethod
    def under_drop_quota(drop):
        number_initial_drops_finished = DropSession.objects.filter(
            drop=drop, state__gt=SessionState.READY_TO_RECEIVE_INITIAL.value
        ).count()
        return number_initial_drops_finished < drop.initial_coin_limit

    def minimum_coin_available(self, drop):
        unspent_pmob = self.payments.get_unspent_pmob()
        return unspent_pmob >= (
            drop.initial_coin_amount_pmob + int(self.payments.get_minimum_fee_pmob())
        )

    @staticmethod
    def get_active_drop():
        active_drops = Drop.objects.filter(start_time__lte=timezone.now()).filter(
            end_time__gte=timezone.now()
        )
        return active_drops.first()

    @staticmethod
    def get_customer_store_preferences(customer, store_to_check):
        try:
            customer_store_preferences = CustomerStorePreferences.objects.get(
                customer=customer, store=store_to_check
            )
            return customer_store_preferences
        except (Exception,):
            return None

    def customer_has_store_preferences(self, customer):
        try:
            _ = CustomerStorePreferences.objects.get(
                customer=customer, store=self.store
            )
            return True
        except (Exception,):
            return False

    @staticmethod
    def customer_has_completed_airdrop(customer, drop):
        try:
            _completed_drop_session = DropSession.objects.get(
                customer=customer, drop=drop, state=SessionState.COMPLETED.value
            )
            return True
        except (Exception,):
            return False

    @staticmethod
    def customer_has_completed_airdrop_with_error(customer, drop):
        try:
            _completed_drop_session = DropSession.objects.get(
                customer=customer, drop=drop, state=SessionState.OUT_OF_MOB.value
            )
            return True
        except (Exception,):
            return False

    @staticmethod
    def customer_has_completed_item_drop(customer, drop):
        try:
            DropSession.objects.get(
                customer=customer, drop=drop, state=ItemSessionState.COMPLETED.value
            )
            return True
        except (Exception,):
            return False

    def handle_drop_session_allow_contact_requested(self, message, drop_session):
        if message.text.lower() in ("y", "yes"):
            customer_prefs = CustomerStorePreferences.objects.create(
                customer=drop_session.customer, store=self.store, allows_contact=True
            )
            drop_session.state = SessionState.COMPLETED.value
            drop_session.save()
            self.messenger.log_and_send_message(
                drop_session.customer, message.source, ChatStrings.BYE
            )
            return

        if message.text.lower() == "n" or message.text.lower() == "no":
            customer_prefs = CustomerStorePreferences(
                customer=drop_session.customer, store=self.store, allows_contact=False
            )
            customer_prefs.save()
            drop_session.state = SessionState.COMPLETED.value
            drop_session.save()
            self.messenger.log_and_send_message(
                drop_session.customer, message.source, ChatStrings.BYE
            )
            return

        if message.text.lower() == "p" or message.text.lower() == "privacy":
            self.messenger.log_and_send_message(
                drop_session.customer,
                message.source,
                ChatStrings.PRIVACY_POLICY_REPROMPT.format(url=self.store.privacy_policy_url)
            )
            return

        if message.text.lower() == "help":
            self.messenger.log_and_send_message(
                drop_session.customer,
                message.source,
                ChatStrings.HELP
            )
            return

        self.messenger.log_and_send_message(
            drop_session.customer,
            message.source,
            ChatStrings.HELP
        )

    def handle_drop_session_ready_to_receive(self, message, drop_session):
        if (
            message.text.lower() == "n"
            or message.text.lower() == "no"
            or message.text.lower() == "cancel"
        ):
            drop_session.state = SessionState.CANCELLED.value
            drop_session.save()
            self.messenger.log_and_send_message(
                drop_session.customer,
                message.source,
                ChatStrings.SESSION_CANCELLED
            )
            return

        if message.text.lower() == "y" or message.text.lower() == "yes":
            if not self.under_drop_quota(drop_session.drop):
                self.messenger.log_and_send_message(
                    drop_session.customer,
                    message.source,
                    ChatStrings.AIRDROP_OVER
                )
                drop_session.state = SessionState.COMPLETED.value
                drop_session.save()
                return

            if not self.minimum_coin_available(drop_session.drop):
                self.messenger.log_and_send_message(
                    drop_session.customer,
                    message.source,
                    ChatStrings.AIRDROP_OVER
                )
                drop_session.state = SessionState.COMPLETED.value
                drop_session.save()
                return

            amount_in_mob = mc.pmob2mob(drop_session.drop.initial_coin_amount_pmob)
            value_in_currency = amount_in_mob * Decimal(
                drop_session.drop.conversion_rate_mob_to_currency
            )
            self.payments.send_mob_to_customer(drop_session.customer, message.source, amount_in_mob, True)
            self.messenger.log_and_send_message(
                drop_session.customer,
                message.source,
                ChatStrings.AIRDROP_INITIALIZE.format(
                    amount=amount_in_mob.normalize(),
                    symbol=drop_session.drop.currency_symbol,
                    value=value_in_currency
                )
            )
            self.messenger.log_and_send_message(
                drop_session.customer,
                message.source,
                ChatStrings.PAY_HELP
            )

            drop_session.state = SessionState.WAITING_FOR_BONUS_TRANSACTION.value
            drop_session.save()
            return

        if message.text.lower() == "help":
            self.messenger.log_and_send_message(
                drop_session.customer,
                message.source,
                ChatStrings.YES_NO_HELP
            )
            return

        self.messenger.log_and_send_message(
            drop_session.customer,
            message.source,
            ChatStrings.YES_NO_HELP
        )
