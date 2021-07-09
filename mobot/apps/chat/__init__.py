import mobilecoin
import pytz

from django.conf import settings
from django.utils import timezone

from mobot.apps.drop import Drop
from mobot.apps.chat.models import Message, MessageDirection
from mobot.apps.merchant_services.models import Customer, CustomerStorePreferences, DropSession, Campaign
from mobot.signald_client import Signal



def _signald_to_fullservice(receipt):
    return {
        "object": "receiver_receipt",
        "public_key": receipt['txo_public_key'],
        "confirmation": receipt['txo_confirmation'],
        "tombstone_block": str(receipt['tombstone']),
        "amount": {
            "object": "amount",
            "commitment": receipt['amount_commitment'],
            "masked_value": str(receipt['amount_masked'])
        }
    }


class Mobot:
    """Actual handlers"""
    def __init__(self, signal: Signal, drop: Drop, mobilecoin_client: mobilecoin.Client):
        self.mobilecoin_client = mobilecoin_client
        self.drop = drop
        self.signal = signal if signal else self._get_signal_client()
    
    def _register_handlers(self):

    def _get_signal_client(self):
        return Signal(self.store.phone_number, socket_path=(settings.SIGNALD_ADDRESS, int(settings.SIGNALD_PORT)))

    def self.log_and_send_message(self, customer: Customer, source: str, text: str):
        sent_message = Message(customer=customer, store=self.drop.store, text=text, direction=MessageDirection.MESSAGE_DIRECTION_SENT)
        sent_message.save()
        self.signal.send_message(source, text)

    def _get_signal_profile_name(self, source: str):
        customer_signal_profile = self.signal.get_profile(source, True)
        customer_name = customer_signal_profile.get("data", {}).get("name")
        if not customer_name:
            self.logger.error("Unable to get signal profile name")
        return customer_name

    def _get_payments_address(self, source: str):
        customer_signal_profile = self.signal.get_profile(source, True)
        customer_payments_address = customer_signal_profile.get("data", {}).get("paymentsAddress")
        if not customer_payments_address:
            self.logger.error("Unable to get payments address")
        return customer_payments_address

    @signal.chat_handler("balance")
    def account_balance(self, message, match):
        account_balance_response = self.mobilecoin_client.get_balance_for_account(settings.ACCOUNT_ID)
        unspent_pmob = account_balance_response['unspent_pmob']
        unspent_mob = mobilecoin.pmob2mob(unspent_pmob)
        return f'You have {unspent_mob} unspent MOB'

    @signal.payment_handler
    def _handler_handle_payment(self, source, receipt):
        receipt_status = None
        transaction_status = "TransactionPending"

        while transaction_status == "TransactionPending":
            receipt_status = self.mobilecoin_client.check_receiver_receipt_status(settings.STORE_ADDRESS, _signald_to_fullservice(receipt))
            transaction_status = receipt_status["receipt_transaction_status"]

        if transaction_status != "TransactionSuccess":
            return "The transaction failed!"

        amount_paid_mob = mobilecoin.pmob2mob(receipt_status["txo"]["value_pmob"])
        refund_customer(source, amount_paid_mob, False)

    # catch all chat handler, will perform our own routing from here
    @signal.chat_handler("")
    def _handler_chat_router(self, message, match):
        customer, _is_new_customer = Customer.objects.get_or_create(phone_number=message.source['number'])
        received_message = Message(customer=customer, store=self.store, direction=MessageDirection.MESSAGE_DIRECTION_RECEIVED,
                                   text=message.text)
        received_message.save()

        try:
            drop_session = Campaign.objects.get(customer=customer, state__gte=DropSession.State.STARTED)

            if drop_session.state == DropSession.State.ALLOW_CONTACT_REQUESTED:
                if message.text.lower() == "y" or message.text.lower() == "yes":
                    customer_prefs = CustomerStorePreferences(customer=customer, store=self.store, allows_contact=True)
                    customer_prefs.save()
                    drop_session.state = DropSession.State.COMPLETED
                    drop_session.save()
                    self.log_and_send_message(customer, message.source, "Thanks! MOBot OUT. Buh-bye")
                    return

                if message.text.lower() == "n" or message.text.lower() == "no":
                    customer_prefs = CustomerStorePreferences(customer=customer, store=self.store, allows_contact=False)
                    customer_prefs.save()
                    drop_session.state = DropSession.State.COMPLETED
                    drop_session.save()
                    self.log_and_send_message(customer, message.source, "Thanks! MOBot OUT. Buh-bye")
                    return

                if message.text.lower().startswith("p"):
                    self.log_and_send_message(customer, message.source,
                                         "Our privacy policy is available here: {0}\n\nWould you like to receive alerts for future drops?".format(
                                             store.privacy_policy_url))
                    return

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

        # if customer.received_sticker_pack:
        #     self.log_and_send_message(customer, message.source, "Looks like you've already received a sticker pack! MOBot OUT. Buh-bye")
        #     return

        drops_to_advertise = Drop.objects.filter(advertisment_start_time__lte=timezone.now()).filter(
            start_time__gt=timezone.now())

        if len(drops_to_advertise) > 0:
            drop_to_advertise = drops_to_advertise[0]

            if not customer.phone_number.startswith(drop_to_advertise.number_restriction):
                self.log_and_send_message(customer, message.source,
                                     "Hi! MOBot here.\n\nSorry, we are not yet available in your country")
                return
            bst_time = drop_to_advertise.start_time.astimezone(pytz.timezone(drop_to_advertise.timezone))
            response_message = "Hi! MOBot here.\n\nWe're currently closed.\n\nCome back on {0} at {1} for {2}".format(
                bst_time.strftime("%A, %b %d"), bst_time.strftime("%-I:%M %p %Z"), drop_to_advertise.item.description)
            self.log_and_send_message(customer, message.source, response_message)
            return

        active_drops = Drop.objects.filter(start_time__lte=timezone.now()).filter(end_time__gte=timezone.now())
        if len(active_drops) == 0:
            self.log_and_send_message(customer, message.source, "Hi! MOBot here.\n\nWe're currently closed. Buh-Bye!")
            return

        active_drop = active_drops[0]
        if not customer.phone_number.startswith(active_drop.number_restriction):
            self.log_and_send_message(customer, message.source,
                                 "Hi! MOBot here.\n\nSorry, we are not yet available in your country")
            return

        customer_payments_address = get_payments_address(message.source)
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
            new_drop_session = DropSession(customer=customer, drop=active_drop, state=DropSession.State.COMPLETED)
            new_drop_session.save()
            self.log_and_send_message(customer, message.source, "Thanks! MOBot OUT. Buh-bye")
            return
        except:
            new_drop_session = DropSession(customer=customer, drop=active_drop,
                                           state=DropSession.State.ALLOW_CONTACT_REQUESTED)
            new_drop_session.save()
            self.log_and_send_message(customer, message.source, "Would you like to receive alerts for future drops?")
            return

    def run(self):
        self.signal.run_chat(True)