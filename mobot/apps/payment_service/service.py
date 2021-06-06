import mobilecoin
from typing import Protocol, NewType
from dataclasses import dataclass
from dacite import from_dict

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


class PaymentService(Protocol):
    client: mobilecoin.Client

    # def submit_payment_intent(self, account_id: AccountId, amount: PaymentAmount, to_address: Address) -> Payment:
    #     transaction_log = from_dict(TransactionLog, data=self.client.build_and_submit_transaction(account_id, amount, to_address))
    #     transaction = Transaction(transaction_id=transaction_log.txo_id)
    #     transaction.save()
    #     payment = Payment(transaction=transaction)
    #     payment.save()
    #     return payment

    def get_payment_status(self, payment: Payment) -> Payment:
        ## TODO: Brian: Help with format of this returned object
        txo: Transaction = self.client.check_receiver_receipt_status(address=Address, receipt=payment.transaction.receipt)


    ## All following methods are private to Payment Service
    def submit_payment_to_user(self, account_id: AccountId, amount_in_mob: float, customer_payments_address: Address) -> Transaction:
        tx_proposal = self.client.build_transaction(account_id, amount_in_mob, customer_payments_address)
        txo_id = self._submit_transaction(tx_proposal, account_id)
        receipt = self._create_receiver_receipt(tx_proposal)
        transaction = Transaction(transaction_id=txo_id, transaction_amt=amount_in_mob, receipt=receipt)

        # Todo: Extract the polling
        try:
            self.client.poll_txo(txo_id)
            transaction.transaction_status = transaction.Status.TransactionSuccess
        except Exception:
            transaction.transaction_status = transaction.Status.Other
            print("TxOut did not land yet, id: " + txo_id)
        finally:
            transaction.save()

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


