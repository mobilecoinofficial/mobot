import logging
import time

from typing import Protocol, NewType
from dataclasses import dataclass
from dacite import from_dict
from concurrent.futures import ThreadPoolExecutor
from django.conf import settings

import mobilecoin

# Type aliases
from mobot.apps.payment_service.models import *


AccountId = NewType('AccountId', str) # Full service account ID
PaymentAmount = NewType('PaymentAmount', float)
Receipt = NewType('Receipt', str) # is this true?
TransactionId = NewType('TransactionId', str) # Hex transaction ID

# TODO: BRIAN: NEED HELP WITH THIS STRUCT
@dataclass
class TransactionLog:
    value_pmob: float
    txo_id: str
    completed: bool
    receipt: Receipt

def _signald_to_fullservice(r):
    return {
        "object": "receiver_receipt",
        "public_key": r['txo_public_key'],
        "confirmation": r['txo_confirmation'],
        "tombstone_block": str(r['tombstone']),
        "amount": {
            "object": "amount",
            "commitment": r['amount_commitment'],
            "masked_value": str(r['amount_masked'])
        }
    }


class TransactionTimeoutException(Exception):
    """For use when this is better"""
    pass


class PaymentService:

    def __init__(self, mobilecoin_client: mobilecoin.Client, account_id=None):
        self.client = mobilecoin_client
        self.executor = ThreadPoolExecutor(4)
        self.account_id = account_id if account_id else settings.ACCOUNT_ID
        self._futures = []
        self.logger = logging.getLogger("PaymentService")

    def submit_payment_intent(self, amount: PaymentAmount, to_address: str) -> Payment:
        transaction_log = from_dict(TransactionLog, data=self.client.build_and_submit_transaction(self.account_id, amount, to_address))
        transaction = Transaction(transaction_id=transaction_log.txo_id)
        transaction.save()
        payment = Payment(transaction=transaction)
        payment.save()
        return payment

    def get_payment_status(self, payment: Payment) -> Payment:
        ## TODO: Brian: Help with format of this returned object
        return self.get_payment_result(transaction=payment.transaction)

    def get_payment_result(self, receipt, max_time_secs: float = 30) -> Payment:
        transaction_status = "TransactionPending"
        receipt_status = {}

        while transaction_status == "TransactionPending":
            receipt_status = self.client.check_receiver_receipt_status(self.account_id, _signald_to_fullservice(receipt))
            transaction_status = receipt_status["receipt_transaction_status"]

            if transaction_status != "TransactionSuccess":
                return "The transaction failed!"


        amount_paid_mob = mobilecoin.pmob2mob(receipt_status.get("txo").get("value_pmob"))

        payment = Payment.objects.create(amount=amount_paid_mob,
                                         state=Payment.Status.PAYMENT_RECEIVED if amount_paid_mob else Payment.Status.PAYMENT_FAILED)

        return payment

    def submit_payment_to_user(self, amount_in_mob: float, customer_payments_address: str) -> Payment:
        tx_proposal = self.client.build_transaction(self.account_id, amount_in_mob, customer_payments_address)
        txo_id = self._submit_transaction(tx_proposal, self.account_id)
        receipt = self._create_receiver_receipt(tx_proposal)
        payment = self.get_payment_result(receipt)
        return payment

    def _create_receiver_receipt(self, tx_proposal) -> Receipt:
        receiver_receipts = self.client.create_receiver_receipts(tx_proposal)
        # I'm assuming there will only be one receiver receipt (not including change tx out).
        if len(receiver_receipts) > 1:
            raise ValueError("Found more than one txout for this chat bot-initiated transaction.")
        return receiver_receipts[0]

    def _submit_transaction(self, tx_proposal, account_id) -> TransactionId:
        transaction_log = self.client.submit_transaction(tx_proposal, account_id)
        list_of_txos = transaction_log["output_txos"]

        # I'm assuming there will only be one tx out (not including change tx out).
        if len(list_of_txos) > 1:
            raise ValueError("Found more than one txout for this chat bot-initiated transaction.")

        return list_of_txos[0]["txo_id_hex"]

    def get_transaction_proposal(self, amount_in_mob: float, customer_payments_address = str):
        return self.client.build_transaction(account_id=self.account_id, amount=amount_in_mob, to_address=customer_payments_address)

