from typing import Protocol, Optional
from string import Template
from django.conf import settings
from mobilecoin import Client
from mobot.apps.signald_client import Signal


class Source(Protocol):
    @property
    def account_id(self) -> str:
        """
        Some identifier, public for the user
        """
        ...

    def payments_address(self) -> str: ...


class MerchantSource(Source):
    @property
    def store_number(self) -> str: ...

    @property
    def private_account_id(self) -> str:
        """
        Return the private account id used to
        """
        ...


class SignalSource(Source):
    def __init__(self, signal: Signal):
        self.signal = signal

    @property
    def signal_number(self) -> str: ...

    @property
    def account_id(self) -> str: return self.signal_number

    @property
    def payments_address(self) -> str:
        customer_signal_profile = self.signal.get_profile(self.signal_number, True)
        customer_payments_address = customer_signal_profile['data']['paymentsAddress']
        if customer_payments_address is None:
            return None
        return customer_payments_address


class PaymentBackend(Protocol):
    ...


class MOBPaymentBackend(PaymentBackend):
    ...


class FullServiceBackend(MOBPaymentBackend):
    def __init__(self, mc_client: Client):
        self.mcc = mc_client if mc_client else Client(url=settings.FULL_SERVICE_URL)

    def full_service_id(self) -> str:
        """
        The secret ID of the full-service wallet used to send and receive MOB
        """
        ...




class MerchantSource(Source, FullServiceBackend):
    def _refund_template(self) -> Template: ...

    def _refund_message(self, customer_source: Source, amount_mob: float, message: Optional[Template]) -> str:
        ...

    def refund_customer(self, customer_source: Source, amount_mob: float, cover_transaction_fee: float) -> bool: ...


class SignalMerchantSource(MerchantSource, SignalSource):
    ...


class PaymentService(Protocol):
    """Allows payment processing"""

    def __init__(self, merchant_source: MerchantSource,):
        """Constructor for PaymentService"""
        self.merchant_source = merchant_source

    def send_mob_to_user(self, merchant_source: MerchantSource, amount_in_mob: float, user_source: Source):
        """
        @param merchant_source: Merchant payment source
        @type merchant_source: MerchantSource
        @param user_source: who we're sending refund to
        @type user_source: Source
        """
        tx_proposal = self.mcc.build_transaction(merchant_source.account_id, amount_in_mob, user_source.payments_address())
        txo_id = submit_transaction(tx_proposal, account_id)
        for _ in range(10):
            try:
                mcc.get_txo(txo_id)
                break
            except Exception:
                print("TxOut did not land yet, id: " + txo_id)
                pass
            time.sleep(1.0)
        else:
            signal.send_message(source, "couldn't generate a receipt, please contact us if you didn't get a refund!")
            return

        send_payment_receipt(source, tx_proposal)
        signal.send_message(source, "{} MOB refunded".format(float(amount_in_mob)))

