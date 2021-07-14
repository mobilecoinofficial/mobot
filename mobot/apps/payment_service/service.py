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
Address = NewType('Address', str)
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
    pass

class PaymentService:

    def __init__(self, mobilecoin_client: mobilecoin.Client):
        self.mobilecoin_client = mobilecoin_client
        self.executor = ThreadPoolExecutor(4)
        self._futures = []
        self.logger = logging.getLogger("PaymentService")

    def submit_payment_intent(self, account_id: AccountId, amount: PaymentAmount, to_address: Address) -> Payment:
        transaction_log = from_dict(TransactionLog, data=self.client.build_and_submit_transaction(account_id, amount, to_address))
        transaction = Transaction(transaction_id=transaction_log.txo_id)
        transaction.save()
        payment = Payment(transaction=transaction)
        payment.save()
        return payment

    def get_payment_status(self, payment: Payment) -> Payment:
        ## TODO: Brian: Help with format of this returned object
        txo: Transaction = self.client.check_receiver_receipt_status(address=Address, receipt=payment.transaction.receipt)

    def get_payment_result(self, transaction: Transaction, max_time_secs: float = 30) -> Payment:
        start_time = time.time()
        time_elapsed = 0
        attempts = 0
        try:
            while transaction.transaction_status == transaction.Status.TransactionPending:
                time_elapsed = time.time() - start_time
                if time_elapsed > max_time_secs:
                    raise TransactionTimeoutException(f"Transaction polling lasted longer than max time {max_time_secs}")
                try:
                    self.client.poll_txo(transaction.transaction_id)
                except Exception as e:
                    transaction.transaction_status = transaction.Status.Other
                    self.logger.exception("TxOut did not land yet")
                    attempts += 1
                    time.sleep(attempts * 0.5)
                finally:
                    transaction.save()
        except TransactionTimeoutException as e:
            self.logger.exception(f"Failed to get payment result of {transaction} before timeout.")

    def submit_payment_to_user(self, account_id: AccountId, amount_in_mob: float, customer_payments_address: Address) -> Transaction:
        tx_proposal = self.client.build_transaction(account_id, amount_in_mob, customer_payments_address)
        txo_id = self._submit_transaction(tx_proposal, account_id)
        receipt = self._create_receiver_receipt(tx_proposal)
        transaction = Transaction(transaction_id=txo_id, transaction_amt=amount_in_mob, receipt=receipt)

        result_future = self.executor.submit(self.get_payment_result, transaction)
        self._futures.append(result_future)

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


