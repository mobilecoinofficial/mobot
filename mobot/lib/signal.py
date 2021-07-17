from .logs import *

from mobot.signald_client import Signal


class SignalCustomerDataClient:
    def __init__(self, signal: Signal):
        self.signal = signal
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_signal_profile_name(self, source: str):
        customer_signal_profile = self.signal.get_profile(source, True)
        try:
            customer_name = customer_signal_profile['data']['name']
            return customer_name
        except KeyError:
            self.logger.error(f"No profile found for {source}")
            return None

    def get_payments_address(self, source: str):
        customer_signal_profile = self.signal.get_profile(source, True)
        print(customer_signal_profile)
        try:
            customer_payments_address = customer_signal_profile['data']['paymentsAddress']
            return customer_payments_address
        except KeyError:
            self.logger.error(f"No profile found for {source}")
            return None

