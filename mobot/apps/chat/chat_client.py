from decimal import Decimal
from enum import Enum
from typing import Callable, Iterable
from dataclasses import dataclass

import mobilecoin
import pytz

from django.conf import settings
from django.utils import timezone

from mobot.apps.drop.campaign_drop import Drop
from mobot.apps.chat.models import Message, MessageDirection
from mobot.apps.merchant_services.models import Customer, CustomerStorePreferences, DropSession, Campaign
from mobot.signald_client import Signal
from mobot.lib.signal import SignalCustomerDataClient
from mobot.signald_client.types import Message
from mobot.signald_client.main import QueueSubscriber

TRANSACTION_FAILED = "The transaction failed!"
GOODBYE = "Thanks! MOBot OUT. Buh-bye"
NO_INFO_FUTURE_DROPS = "You will no longer receive notifications about future drops."
NOT_RECEIVING_NOTIFICATIONS = "You are not currently receiving any notifications"


class TransactionStatus(str, Enum):
    TRANSACTION_SUCCESS = "TransactionSuccess"
    TRANSACTION_PENDING = "TransactionPending"



class MobotMessage(str, Enum):
    YES = "y"
    NO = "n"
    CANCEL = "cancel"
    UNSUBSCRIBE = "unsubscribe"

class Mobot:
    def __init__(self, name: str, signal: Signal, drop: Drop, mobilecoin_client: mobilecoin.Client):
        self.signal = signal
        self.drop = drop
        self.mobilecoin_client = mobilecoin_client
        self.store = self.drop.store
        self.name = name
        self.customer_data_client = SignalCustomerDataClient(signal=self.signal)
        self._subscriber = QueueSubscriber(name)
        self.signal.register_subscriber(self._subscriber)
        self._callbacks = []

    def get_customer_session(self, phone_number: str):
        customer, _is_new_customer = Customer.objects.get_or_create(phone_number=phone_number)

    def log_and_send_message(self, customer: Customer, text: str):
        sent_message = Message(customer=customer, store=Mobot.store, text=text,
                               direction=MessageDirection.MESSAGE_DIRECTION_SENT)
        sent_message.save()
        Mobot.signal.send_message(str(customer.phone_number), text)

    def privacy_policy_handler(self, message, _match):
        customer, _is_new = Customer.objects.get_or_create(phone_number=message.source['number'])
        Mobot.log_and_send_message(customer, message.source, Mobot.store.privacy_policy_url)
        return

    def register_handler(self, regex, method):
        self.signal.register_chat_handler(regex, method)

    def register_handlers(self):
        Mobot.signal.register_chat_handler("unsubscribe", Mobot.unsubscribe_handler)
        Mobot.signal.register_chat_handler("", Mobot.base_chat_router)
        Mobot.signal.register_chat_handler("p", Mobot.privacy_policy_handler)
        Mobot.signal.payment_handler(self.handle_payment)

    def unsubscribe_handler(message, _match):
        customer, _is_new = Customer.objects.get_or_create(phone_number=message.source['number'])
        store_preferences, _is_new = CustomerStorePreferences.objects.get_or_create(customer=customer,
                                                                                    store=self.store)

        if not store_preferences.allows_contact:
            Mobot.log_and_send_message(customer, message.source, NOT_RECEIVING_NOTIFICATIONS)
            return

        store_preferences.allows_contact = False
        store_preferences.save()

        self.log_and_send_message(customer, message.source,
                                  NO_INFO_FUTURE_DROPS)
    @staticmethod
    def handle_payment(source, receipt):
        receipt_status = None
        transaction_status = TransactionStatus.TRANSACTION_PENDING

        while transaction_status == TransactionStatus.TRANSACTION_PENDING:
            receipt_status = Mobot.mobilecoin_client.check_receiver_receipt_status(settings.STORE_ADDRESS,
                                                                                  _signald_to_fullservice(receipt))
            transaction_status = receipt_status["receipt_transaction_status"]

        if transaction_status != TransactionStatus.TRANSACTION_SUCCESS:
            return TRANSACTION_FAILED

        amount_paid_mob = mobilecoin.pmob2mob(receipt_status["txo"]["value_pmob"])
        Mobot.send_mob_to_customer(source, amount_paid_mob, False)

    def set_customer_preferences(self, customer: Customer, allow_contact: bool):
        customer_prefs = CustomerStorePreferences(customer=customer, store=self.store,
                                                  allows_contact=allow_contact)
        customer_prefs.save()


    @staticmethod
    def find_active_drop_for_customer(customer: Customer) -> DropSession:
        return customer.offer_sessions.get(campaign=Mobot.drop.campaign)


    @staticmethod
    def base_chat_router(message, _):
        customer, _is_new_customer = Customer.objects.get_or_create(phone_number=message.source['number'])
        received_message = Message(customer=customer, store=self.store,
                                   direction=MessageDirection.MESSAGE_DIRECTION_RECEIVED,
                                   text=message.text)
        received_message.save()

        try:
            drop_session = Campaign.objects.get(customer=customer, state__gte=DropSession.State.STARTED)

            if drop_session.state == DropSession.State.ALLOW_CONTACT_REQUESTED:
                if message.text.lower() == "y" or message.text.lower() == "yes":
                    self.set_customer_preferences(customer=customer, allow_contact=True)
                elif message.text.lower() == "n" or message.text.lower() == "no":
                    self.set_customer_preferences(customer=customer, allow_contact=False)
                drop_session.state = DropSession.State.COMPLETED
                drop_session.save()
                self.log_and_send_message(customer, message.source, GOODBYE)

                if message.text.lower() == "cancel":
                    drop_session.state = DropSession.State.COMPLETED
                    drop_session.save()
                    self.log_and_send_message(customer, message.source, "Your session has been cancelled")
                    return

                self.log_and_send_message(customer, message.source,
                                          "You can type (y)es, (n)o, or (p)rivacy policy\n\nWould you like to receive alerts for future drops?")
                return
        except:
            pass


        try:
            drops_to_advertise = Campaign.objects.get(advertisement_start_time__gte=timezone.now(), end_time__lte=timezone.now())
        except Campaign.DoesNotExist:
            Mobot.log_and_send_message(customer, "Looks like this campaign is over!")

        if len(drops_to_advertise) > 0:
            drop_to_advertise = drops_to_advertise[0]

            if not customer.phone_number.startswith(drop_to_advertise.number_restriction):
                self.log_and_send_message(customer, message.source,
                                          "Hi! MOBot here.\n\nSorry, we are not yet available in your country")
                return
            bst_time = drop_to_advertise.start_time.astimezone(pytz.timezone(drop_to_advertise.timezone))
            response_message = "Hi! MOBot here.\n\nWe're currently closed.\n\nCome back on {0} at {1} for {2}".format(
                bst_time.strftime("%A, %b %d"), bst_time.strftime("%-I:%M %p %Z"),
                drop_to_advertise.item.description)
            self.log_and_send_message(customer, message.source, response_message)
            return

        active_drops = Drop.objects.filter(start_time__lte=timezone.now()).filter(end_time__gte=timezone.now())
        if len(active_drops) == 0:
            self.log_and_send_message(customer, message.source,
                                      "Hi! MOBot here.\n\nWe're currently closed. Buh-Bye!")
            return

        active_drop = active_drops[0]
        if not customer.phone_number.startswith(active_drop.number_restriction):
            self.log_and_send_message(customer, message.source,
                                      "Hi! MOBot here.\n\nSorry, we are not yet available in your country")
            return

        customer_payments_address = self.customer_data_client.get_payments_address(message.source)
        if customer_payments_address is None:
            self.log_and_send_message(customer, message.source,
                                      "Hi! MOBot here.\n\nI'm a bot from MobileCoin that assists in making purchases using Signal Messenger and MobileCoin\n\nUh oh! In-app payments are not enabled \n\nEnable payments to receive {0}\n\nMore info on enabling payments here: https://support.signal.org/hc/en-us/articles/360057625692-In-app-Payments".format(
                                          active_drop.item.description))
            return

        self.log_and_send_message(customer, message.source,
                                  "Looks like you have everything set up! Here's your digital sticker pack")
        self.log_and_send_message(customer, message.source,
                                  "https://signal.art/addstickers/#pack_id=83d4f5b9a0026fa6ffe1b1c0f11a2018&pack_key=6b03ace1a84b31589ce231a74ad914733217cea9ba47a411a9abe531aab8e55a")

        customer.received_sticker_pack = True
        customer.save()

        try:
            _ = CustomerStorePreferences.objects.get(customer=customer, store=self.store)
            new_drop_session = DropSession(customer=customer, drop=active_drop,
                                           state=DropSession.State.COMPLETED)
            new_drop_session.save()
            self.log_and_send_message(customer, message.source, GOODBYE)
            return
        except:
            new_drop_session = DropSession(customer=customer, drop=active_drop,
                                           state=DropSession.State.ALLOW_CONTACT_REQUESTED)
            new_drop_session.save()
            self.log_and_send_message(customer, message.source,
                                      "Would you like to receive alerts for future drops?")
            return

    def send_mob_to_customer(self, source, amount_mob: Decimal, cover_transaction_fee: bool):
        customer = Customer.objects.get(phone_number=source)
        customer_payments_address = self.customer_data_client.get_payments_address(source)
        if customer_payments_address is None:
            self.log_and_send_message(customer,
                                ("""We have a refund for you, but your payments have been deactivated\n
                                 Please contact customer service at {}""").format(self.store.phone_number))
            return

        if not cover_transaction_fee:
            amount_mob = amount_mob - Decimal(mobilecoin.pmob2mob(settings.MINIMUM_FEE_PMOB))

        if amount_mob <= 0:
            self.log_and_send_message(customer,
                                """MOBot here! You sent us an unsolicited payment that we can't return.\n
                                We suggest only sending us payments when we request them and for the amount 
                                requested.""")
            return

        self.send_mob_to_address(source, settings.ACCOUNT_ID, amount_mob, customer_payments_address)





    def handle_privacy_policy(self, drop_session: DropSession):
        customer = drop_session.customer
        self.log_and_send_message(customer, str(customer.phone_number),
                                  "Our privacy policy is available here: {0}\n\nWould you like to receive alerts for future drops?".format(
                                      self.store.privacy_policy_url))
        return

    def handle_cancel(self, drop_session: DropSession):
        def inner():
            drop_session.state = DropSession.State.COMPLETED
            drop_session.save()
            self.log_and_send_message(drop_session.customer, str(drop_session.customer.phone_number), "Your session has been cancelled")
        self.
        



    def run(self):
        self.signal.run_chat(True)


    # catch all chat handler, will perform our own routing from here
