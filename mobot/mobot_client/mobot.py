# Copyright (c) 2021 MobileCoin. All rights reserved.


import os
import full_service_cli as mc
import pytz
import threading

from signald_client import Signal

from mobot_client.logger import SignalMessenger
from mobot_client.models import (
    Customer,
    DropSession,
    CustomerStorePreferences,
    BonusCoin,
    ChatbotSettings,
    Message,
    Order,
    Sku,
)

from mobot_client.drop_session import (
    BaseDropSession,
    SessionState,
    DropType,
    ItemSessionState,
)
from mobot_client.air_drop_session import AirDropSession
from mobot_client.item_drop_session import ItemDropSession
from mobot_client.payments import Payments
from mobot_client.chat_strings import ChatStrings
from mobot_client.timeouts import Timeouts


class MOBot:
    """
    MOBot is the container which holds all of the business logic relevant to a Drop.
    """

    def __init__(self):
        self.store = ChatbotSettings.load().store

        signald_address = os.getenv("SIGNALD_ADDRESS", "127.0.0.1")
        signald_port = os.getenv("SIGNALD_PORT", "15432")
        self.signal = Signal(
            self.store.phone_number, socket_path=(signald_address, int(signald_port))
        )
        self.messenger = SignalMessenger(self.signal, self.store)

        fullservice_address = os.getenv("FULLSERVICE_ADDRESS", "127.0.0.1")
        fullservice_port = os.getenv("FULLSERVICE_PORT", "9090")
        fullservice_url = f"http://{fullservice_address}:{fullservice_port}/wallet"
        self.mcc = mc.Client(url=fullservice_url)

        all_accounts_response = self.mcc.get_all_accounts()
        self.account_id = next(iter(all_accounts_response))
        account_obj = all_accounts_response[self.account_id]
        self.public_address = account_obj["main_address"]

        get_network_status_response = self.mcc.get_network_status()
        self.minimum_fee_pmob = int(get_network_status_response["fee_pmob"])

        self.payments = Payments(
            self.mcc,
            self.minimum_fee_pmob,
            self.account_id,
            self.store,
            self.messenger,
            self.signal,
        )

        self.drop = DropSession(self.store, self.payments, self.messenger)

        self.timeouts = Timeouts(self.messenger,  schedule=3, idle_timeout=10, cancel_timeout=20)

        bot_name = ChatbotSettings.load().name
        bot_avatar_filename = ChatbotSettings.load().avatar_filename
        print("bot_avatar_filename", bot_avatar_filename)
        b64_public_address = mc.utility.b58_wrapper_to_b64_public_address(
            self.public_address
        )

        resp = self.signal.set_profile(
            bot_name, b64_public_address, bot_avatar_filename, True
        )
        print("set profile response", resp)
        if resp.get("error"):
            assert False, resp

        # Chat handlers defined in __init__ so they can be registered with the Signal instance
        @self.signal.payment_handler
        def handle_payment(source, receipt):
            receipt_status = None
            transaction_status = "TransactionPending"

            if isinstance(source, dict):
                source = source["number"]

            print("received receipt", receipt)
            receipt = mc.utility.b64_receipt_to_full_service_receipt(receipt.receipt)

            while transaction_status == "TransactionPending":
                receipt_status = self.mcc.check_receiver_receipt_status(
                    self.public_address, receipt
                )
                transaction_status = receipt_status["receipt_transaction_status"]
                print("Waiting for", receipt, receipt_status)

            if transaction_status != "TransactionSuccess":
                print("failed", transaction_status)
                return "The transaction failed!"

            amount_paid_mob = mc.pmob2mob(receipt_status["txo"]["value_pmob"])

            customer = None
            drop_session = None

            customer, _ = Customer.objects.get_or_create(phone_number=source)
            try:

                drop_session = DropSession.objects.get(
                    customer=customer,
                    drop__drop_type=DropType.AIRDROP.value,
                    state=SessionState.WAITING_FOR_BONUS_TRANSACTION.value,
                )
            except DropSession.DoesNotExist:
                pass
            else:
                air_drop = AirDropSession(self.store, self.payments, self.messenger)
                air_drop.handle_airdrop_payment(
                    source, customer, amount_paid_mob, drop_session
                )
                return

            try:
                drop_session = DropSession.objects.get(
                    customer=customer,
                    drop__drop_type=DropType.ITEM.value,
                    state=ItemSessionState.WAITING_FOR_PAYMENT.value,
                )
            except DropSession.DoesNotExist:
                self.messenger.log_and_send_message(
                    customer, source, ChatStrings.UNSOLICITED_PAYMENT
                )
                self.payments.send_mob_to_customer(source, amount_paid_mob, False)
            else:
                self.payments.handle_item_payment(
                    source, customer, amount_paid_mob, drop_session
                )

        @self.signal.chat_handler("coins")
        def chat_router_coins(message, match):
            bonus_coins = BonusCoin.objects.all()
            for bonus_coin in bonus_coins:
                number_claimed = DropSession.objects.filter(
                    bonus_coin_claimed=bonus_coin
                ).count()
                self.signal.send_message(
                    message.source,
                    f"{number_claimed} out of {bonus_coin.number_available} {mc.pmob2mob(bonus_coin.amount_pmob).normalize()}MOB Bonus Coins claimed ",
                )

        @self.signal.chat_handler("items")
        def chat_router_items(message, match):
            active_drop = BaseDropSession.get_active_drop()
            if active_drop is None:
                return "No active drop to check on items"

            skus = Sku.objects.filter(item=active_drop.item)
            message_to_send = ""
            for sku in skus:
                number_ordered = Order.objects.filter(sku=sku).count()
                message_to_send += (
                    f"{sku.identifier} - {number_ordered} / {sku.quantity} ordered\n"
                )
            self.signal.send_message(message.source, message_to_send)

        @self.signal.chat_handler("unsubscribe")
        def unsubscribe_handler(message, _match):
            customer, _is_new = Customer.objects.get_or_create(
                phone_number=message.source["number"]
            )
            store_preferences, _is_new = CustomerStorePreferences.objects.get_or_create(
                customer=customer, store=self.store
            )

            if not store_preferences.allows_contact:
                self.messenger.log_and_send_message(
                    customer, message.source, ChatStrings.NOTIFICATIONS_OFF
                )
                return

            store_preferences.allows_contact = False
            store_preferences.save()

            self.messenger.log_and_send_message(
                customer, message.source, ChatStrings.DISABLE_NOTIFICATIONS
            )

        @self.signal.chat_handler("subscribe")
        def subscribe_handler(message, _match):
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

        @self.signal.chat_handler("")
        def chat_router(message, match):
            # Store the message
            print("\033[1;33m NOW ROUTING CHAT\033[0m", message)
            customer, _ = Customer.objects.get_or_create(
                phone_number=message.source["number"]
            )
            self.messenger.log_received(message, customer, self.store)
            try:
                active_drop_session = DropSession.objects.get(
                    customer=customer,
                    drop__drop_type=DropType.AIRDROP.value,
                    state__gte=SessionState.READY_TO_RECEIVE_INITIAL.value,
                    state__lt=SessionState.COMPLETED.value,
                )

                if active_drop_session.manual_override:
                    return

                air_drop = AirDropSession(self.store, self.payments, self.messenger)

                air_drop.handle_active_airdrop_drop_session(
                    message, active_drop_session
                )
                return
            except (Exception,):
                pass

            try:
                active_drop_session = DropSession.objects.get(
                    customer=customer,
                    drop__drop_type=DropType.ITEM.value,
                    state__gte=ItemSessionState.WAITING_FOR_PAYMENT.value,
                    state__lt=ItemSessionState.COMPLETED.value,
                )
                print(f"found active drop session in state {active_drop_session.state}")
                if active_drop_session.manual_override:
                    return
            except (Exception,):
                pass
            else:
                item_drop = ItemDropSession(self.store, self.payments, self.messenger)
                item_drop.handle_active_item_drop_session(message, active_drop_session)
                return

            drop_to_advertise = BaseDropSession.get_advertising_drop()
            if drop_to_advertise is not None:
                if not customer.phone_number.startswith(
                        drop_to_advertise.number_restriction
                ):
                    self.messenger.log_and_send_message(
                        customer, message.source, ChatStrings.COUNTRY_RESTRICTED
                    )
                    return
                bst_time = drop_to_advertise.start_time.astimezone(
                    pytz.timezone(drop_to_advertise.timezone)
                )
                response_message = ChatStrings.STORE_CLOSED.format(
                    date=bst_time.strftime("%A, %b %d"),
                    time=bst_time.strftime("%-I:%M %p %Z"),
                    desc=drop_to_advertise.item.description,
                )
                self.messenger.log_and_send_message(
                    customer, message.source, response_message
                )
                return

            active_drop = BaseDropSession.get_active_drop()
            if active_drop is None:
                self.messenger.log_and_send_message(
                    customer, message.source, ChatStrings.STORE_CLOSED_SHORT
                )
                return

            if active_drop.drop_type == DropType.AIRDROP.value:
                air_drop = AirDropSession(self.store, self.payments, self.messenger)
                air_drop.handle_no_active_airdrop_drop_session(
                    customer, message, active_drop
                )

            if active_drop.drop_type == DropType.ITEM.value:
                item_drop = ItemDropSession(self.store, self.payments, self.messenger)
                item_drop.handle_no_active_item_drop_session(
                    customer, message, active_drop
                )

    # FIXME: Handler for cancel/help?

    def run_chat(self):
        print("Starting timeouts thread")
        t = threading.Thread(target=self.timeouts.process_timeouts, args=(), kwargs={})
        t.setDaemon(True)
        t.start()

        print("Now running MOBot chat")
        self.signal.run_chat(True)
