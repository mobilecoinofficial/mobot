import mobilecoin
from typing import Protocol, NewType
from dataclasses import dataclass
from mobot.apps.common.events import Event
from mobot.apps.common.models import BaseMCModel
from django.db import models
from dacite import from_dict
import time

# Type aliases
AccountId = NewType('AccountId', str)
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


class Transaction(BaseMCModel):
    class Status(models.IntegerChoices):
        TransactionSubmitted = -1
        TransactionPending = 0
        TransactionSuccess = 1
        Other = 2

    transaction_id = models.TextField(primary_key=True)
    transaction_amt = models.FloatField(default=0.0)
    transaction_status = models.IntegerField(choices=Status.choices, default=Status.TransactionSubmitted)
    receipt = models.TextField(blank=True)

    @property
    def completed(self):
        return self.transaction_status == self.Status.TransactionSuccess

    @property
    def pending(self):
        return self.transaction_status == self.Status.TransactionPending

    @property
    def failed(self):
        return self.transaction_status == self.Status.Other





class Payment(BaseMCModel):

    class Status(models.IntegerChoices):
        PAYMENT_NOT_SUBMITTED = -1
        PAYMENT_SUBMITTED = 0
        PAYMENT_RECEIVED = 1
        PAYMENT_FAILED = 2

    status = models.IntegerField(choices=Status.choices, default=Status.PAYMENT_NOT_SUBMITTED)
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE)

    def clean(self):
        if self.transaction.failed:
            self.status = Payment.Status.PAYMENT_FAILED
        elif self.transaction.pending:
            self.status = Payment.Status.PAYMENT_SUBMITTED
        elif self.transaction.completed:
            self.status = Payment.Status.PAYMENT_RECEIVED
        self.save()



class PaymentService(Protocol):
    client: mobilecoin.Client

    def _submit_payment_intent(self, account_id: AccountId, amount: PaymentAmount, to_address: Address) -> Payment:
        transaction_log = from_dict(TransactionLog, data=self.client.build_and_submit_transaction(account_id, amount, to_address))
        transaction = Transaction(transaction_id=transaction_log.txo_id)
        return transaction_log

    def get_payment_status(self, payment: Payment) -> Payment:
        txo = self.client.check_receiver_receipt_status(address=Address, receipt=payment.transaction.receipt)

    def send_mob_to_user(self, account_id: AccountId, amount_in_mob: float, customer_payments_address: Address) -> Transaction:
        tx_proposal = self.client.build_transaction(account_id, amount_in_mob, customer_payments_address)
        txo_id = self.submit_transaction(tx_proposal, account_id)
        receipt = self.create_receiver_receipt(tx_proposal)
        transaction = Transaction(transaction_id=txo_id, transaction_amt=amount_in_mob, receipt=receipt)

        # Todo: Extract the polling
        try:
            self.client.poll_txo(txo_id)
            transaction.transaction_status = transaction.Status.TransactionSuccess
        except Exception:
            print("TxOut did not land yet, id: " + txo_id)
        finally:
            transaction.save()



    def create_receiver_receipt(self, tx_proposal) -> Receipt:
        receiver_receipts = self.client.create_receiver_receipts(tx_proposal)
        # I'm assuming there will only be one receiver receipt (not including change tx out).
        if len(receiver_receipts) > 1:
            raise ValueError("Found more than one txout for this chat bot-initiated transaction.")
        return receiver_receipts[0]

    def submit_transaction(self, tx_proposal, account_id) -> TransactionId:
        transaction_log = self.client.submit_transaction(tx_proposal, account_id)
        list_of_txos = transaction_log["output_txos"]

        # I'm assuming there will only be one tx out (not including change tx out).
        if len(list_of_txos) > 1:
            raise ValueError("Found more than one txout for this chat bot-initiated transaction.")

        return list_of_txos[0]["txo_id_hex"]

    def emit_payment_receipt(self, source, tx_proposal) -> Event:
        receiver_receipt = self.create_receiver_receipt(tx_proposal)
        Event.make_event(Event.EventType.PAYMENT_STATE_CHANGE_EVENT, )

