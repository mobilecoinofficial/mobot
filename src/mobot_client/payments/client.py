# Copyright (c) 2021 MobileCoin. All rights reserved.
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional
import asyncio

from django.conf import settings
from django.utils import timezone
from mobilecoin import Client as MCC
import mobilecoin as mc

from mobot_client.models import PaymentStatus, Payment, Customer


class MCClient(MCC):
    def __init__(self):
        super().__init__(settings.FULLSERVICE_URL)
        self.public_address, self.account_id = self._get_default_account_info()
        self.minimum_fee_pmob = self._get_minimum_fee_pmob()
        self.b64_public_address = mc.utility.b58_wrapper_to_b64_public_address(self.public_address)
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

    async def _wait_for_transaction(self, receipt) -> PaymentStatus:
        receipt_status = None
        while transaction_status == PaymentStatus.PENDING:
            receipt_status = self.check_receiver_receipt_status(
                self.public_address, receipt
            )
            transaction_status = PaymentStatus[receipt_status["receipt_transaction_status"]]
            self.logger.info(f"Waiting for {receipt}, current status {receipt_status}")
            time.sleep(2)

        if transaction_status != PaymentStatus.SUCCESS:
            self.logger.error(f"failed {transaction_status}")
            transaction_status = PaymentStatus.FAILURE

        return transaction_status

    async def process_payment(self, payment: Payment) -> Payment:
        transaction_status = await self._wait_for_transaction()
        payment.status = transaction_status
        payment.processed = timezone.now()
        payment.save()
        return payment

    def process_receipt(self, source: str, receipt: str, callback: Optional[Callable]) -> Payment:
        self.logger.info(f"received receipt {receipt}")
        receipt = mc.utility.b64_receipt_to_full_service_receipt(receipt)
        receipt_status = self.check_receiver_receipt_status(
            self.public_address, receipt
        )
        amount_paid_mob = mc.pmob2mob(receipt_status["txo"]["value_pmob"])
        customer, _ = Customer.objects.get_or_create(phone_number=source)
        payment = Payment.objects.create(
            customer=Customer,
            amount_pmob=mc.utility.mob2pmob(amount_paid_mob),
            receipt=receipt,
        )

        def update_status():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(asyncio.ensure_future(self.process_payment(payment)))

        with self._pool as pool:
            tx_future = pool.submit(update_status)
            if callback:
                tx_future.add_done_callback(callback)

        return payment