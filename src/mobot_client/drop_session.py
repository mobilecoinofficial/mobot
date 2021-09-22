# Copyright (c) 2021 MobileCoin. All rights reserved.

import logging
from django.utils import timezone

from mobot_client.chat_strings import ChatStrings
from mobot_client.logger import SignalMessenger
from mobot_client.models import DropSession, Drop, CustomerStorePreferences, Order, Sku, SessionState, Store
from mobot_client.models.messages import Message
from mobot_client.payments import Payments


class BaseDropSession:
    def __init__(self, store: Store, payments: Payments, messenger: SignalMessenger):
        self.store = store
        self.payments = payments
        self.messenger = messenger
        self.logger = logging.getLogger(f"DropSession ({self.store})")


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
            drop=drop, state__gt=SessionState.READY
        ).count()
        return number_initial_drops_finished < drop.initial_coin_limit

    def customer_has_store_preferences(self, customer):
        try:
            _ = CustomerStorePreferences.objects.get(
                customer=customer, store=self.store
            )
            return True
        except (Exception,):
            return False


    @staticmethod
    def customer_has_completed_airdrop_with_error(customer, drop):
        try:
            _completed_drop_session = DropSession.objects.get(
                customer=customer, drop=drop, state=SessionState.OUT_OF_STOCK
            )
            return True
        except (Exception,):
            return False

    @staticmethod
    def customer_has_completed_item_drop(customer, drop):
        try:
            DropSession.objects.get(
                customer=customer, drop=drop, state=SessionState.COMPLETED
            )
            return True
        except (Exception,):
            return False


    def handle_drop_session_allow_contact_requested(self, message, drop_session):
        if message.text.lower() in ("y", "yes"):
            CustomerStorePreferences.objects.create(
                customer=drop_session.customer, store=self.store, allows_contact=True
            )
            drop_session.state = SessionState.COMPLETED
            drop_session.save()
            self.messenger.log_and_send_message(ChatStrings.BYE)
            return

        if message.text.lower() == "n" or message.text.lower() == "no":
            customer_prefs = CustomerStorePreferences(
                customer=drop_session.customer, store=self.store, allows_contact=False
            )
            customer_prefs.save()
            drop_session.state = SessionState.COMPLETED
            drop_session.save()
            self.messenger.log_and_send_message(
                ChatStrings.BYE
            )
            return

        if message.text.lower() == "p" or message.text.lower() == "privacy":
            self.messenger.log_and_send_message(
                ChatStrings.PRIVACY_POLICY_REPROMPT.format(url=self.store.privacy_policy_url),
            )
            return

        if message.text.lower() == "help":
            self.messenger.log_and_send_message(
                drop_session.customer,
                ChatStrings.HELP
            )
            return

        self.messenger.log_and_send_message(
            ChatStrings.HELP
        )

    def handle_cancel(self, message, drop_session: DropSession):
        drop_session.state = SessionState.CANCELLED
        drop_session.save()
        self.messenger.log_and_send_message(
            ChatStrings.SESSION_CANCELLED
        )

    def handle_privacy_policy_request(self, message, drop_session: DropSession):
        privacy_policy_url = drop_session.drop.store.privacy_policy_url
        self.messenger.log_and_send_message(
            ChatStrings.PRIVACY_POLICY.format(url=privacy_policy_url),
        )
