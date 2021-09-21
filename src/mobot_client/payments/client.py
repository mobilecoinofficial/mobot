# Copyright (c) 2021 MobileCoin. All rights reserved.
import logging
import time

from concurrent.futures import ThreadPoolExecutor

from django.utils import timezone
import mc_util as mc

from mobot_client.models.messages import PaymentStatus, Payment, Message, PaymentVerification, ProcessingError

from mobilecoin import Client
from django.conf import settings


class PaymentClientException(Exception):
    pass


class TransactionCheckException(PaymentClientException):
    pass


class CheckReceiptException(PaymentClientException):
    pass



class MCClient(Client):
    def __init__(self):
        super().__init__(settings.FULLSERVICE_URL)
        self.public_address, self.account_id = self._get_default_account_info()
        self.minimum_fee_pmob = self._get_minimum_fee_pmob()
        self.b64_public_address = mc.b58_wrapper_to_b64_public_address(self.public_address)
        self.logger = logging.getLogger("MCClient")
        self._pool = ThreadPoolExecutor(max_workers=settings.PAYMENT_THREADS)

    def _get_minimum_fee_pmob(self):
        get_network_status_response = self.get_network_status()
        return int(get_network_status_response["fee_pmob"])

    def _get_default_account_info(self) -> (str, str):
        accounts = self.get_all_accounts()
        account_id = next(iter(accounts))
        account_obj = accounts[account_id]
        public_address = account_obj["main_address"]
        return public_address, account_id

    def check_receiver_receipt_status(self, address, receipt):
        try:
            return super().check_receiver_receipt_status(address, receipt)
        except Exception as e:
            self.logger.exception("Exception raised when checking receipt")
            raise CheckReceiptException(str(e))

    def _wait_for_transaction(self, payment: Payment) -> Payment:
        receipt = payment.signal_payment.receipt
        transaction_status = PaymentStatus.TransactionPending
        while transaction_status == PaymentStatus.TransactionPending:
            receipt_status = self.get_receipt_status(
                receipt
            )
            transaction_status = PaymentStatus[receipt_status["receipt_transaction_status"]]
            self.logger.info(f"Waiting for {receipt}, current status {receipt_status}")
            payment.status = transaction_status
            payment.save()
            time.sleep(2)

        if transaction_status != PaymentStatus.TransactionSuccess:
            self.logger.error(f"failed {transaction_status}")
            transaction_status = PaymentStatus.Failure
            payment.status = transaction_status
            payment.save()

        return payment

    def process_payment(self, payment: Payment) -> Payment:
        self.logger.info(f"Processing payment {payment}")
        try:
            payment = self._wait_for_transaction(payment)
            payment.processed = timezone.now()
        except PaymentClientException as e:
            from traceback import format_exc
            self.logger.exception("Got an error processing payment")
            payment.status = PaymentStatus.Failure
            ProcessingError.objects.create(
                message=payment.message,
                exception=str(e.__class__.__name__),
                tb=str(format_exc())
            )
        return payment

    def get_receipt_status(self, receipt: str) -> dict:
        try:
            mc.b64_receipt_to_full_service_receipt(receipt)
            self.logger.info(f"checking Receiver status")
            receipt_status = self.check_receiver_receipt_status(
                self.public_address, receipt
            )
            return receipt_status
        except Exception as e:
            self.logger.exception("Exception getting receipt status")
            raise CheckReceiptException(str(e))

    def process_signal_payment(self, message: Message) -> Payment:
        signal_payment = message.raw.payment
        receipt = signal_payment.receipt
        self.logger.info(f"received receipt {receipt} for customer {message.customer}")
        try:
            receipt_status = self.get_receipt_status(receipt)
        except PaymentClientException as e:
            self.logger.exception("Exception getting receipt status")
            raise e
        else:
            amount_paid_mob = mc.pmob2mob(receipt_status["txo"]["value_pmob"])
            txo_id = receipt_status["txo"]["txo_id"]

            payment = Payment.objects.create(
                amount_pmob=mc.mob2pmob(amount_paid_mob),
                txo_id=txo_id,
                signal_payment=signal_payment,
            )
            message.payment = payment
            try:
                processed_payment = self.process_payment(payment)
                return processed_payment
            except PaymentClientException as e:
                self.logger.exception("Exception processing payment status")
                raise e
