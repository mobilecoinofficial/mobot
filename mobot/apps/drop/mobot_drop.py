import logging
from typing import Optional

from mobot.apps.merchant_services.models import Store, Campaign, Customer, DropSession
from mobot.signald_client import Signal
from django.conf import settings
from .models import Message


SESSION_STATE_CANCELLED = -1
SESSION_STATE_READY_TO_RECEIVE_INITIAL = 0
SESSION_STATE_WAITING_FOR_BONUS_TRANSACTION = 1
SESSION_STATE_ALLOW_CONTACT_REQUESTED = 2
SESSION_STATE_COMPLETED = 3

MESSAGE_DIRECTION_RECEIVED = 0
MESSAGE_DIRECTION_SENT = 1


class MobotDrop:
    def __init__(self, campaign: Campaign, signal: Signal):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.campaign = campaign
        self.store = campaign.store
        self.signal = signal if signal else self._get_signal_client()

    def _get_signal_client(self):
        return Signal(self.store.phone_number, socket_path=(settings.SIGNALD_ADDRESS, int(settings.SIGNALD_PORT)))

    def log_and_send_message(self, customer: Customer, source: str, text: str):
        sent_message = Message(customer=customer, store=self.store, text=text, direction=MESSAGE_DIRECTION_SENT)
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

    def _find_current_session(self, customer: Customer) -> Optional[DropSession]:
        try:
            session = DropSession.objects.get(customer=customer)
            return session
        except Customer.DoesNotExist:
            self.logger.exception(f"Session for {customer} doesn't exist yet")

    def _register_new_customer(self, customer: Customer):
        pass

    def run(self):
        self.signal.run_chat(True)
