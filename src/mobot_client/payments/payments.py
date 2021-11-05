# Copyright (c) 2021 MobileCoin. All rights reserved.
from decimal import Decimal
import logging
from functools import cached_property
from typing import Optional, Union

import mc_util as mc
import tenacity
from signald import Signal

from mobot_client.logger import SignalMessenger
from mobot_client.models import (
    SessionState,
    Store,
    DropSession, Customer,
)
from mobot_client.models.messages import (
    Payment,
    MobotResponse, Direction, SignalPayment, PaymentStatus, Message, MessageStatus,
)
from mobot_client.chat_strings import ChatStrings
from mobot_client.payments.client import MCClient
from mobot_client.utils import TimerFactory
from mobot_client.core.context import ChatContext


class PaymentException(Exception):
    pass


class NotEnoughFundsException(PaymentException):
    pass


class CustomerPaymentsAddressError(PaymentException):
    pass


class ExceptionSendingReceipt(PaymentException):
    pass


class Payments:
    """The Payments class handles the logic relevant to sending MOB and handling receipts."""

    def __init__(
            self, mobilecoin_client: MCClient, store: Store, messenger: SignalMessenger, signal: Signal
    ):
        self.mcc = mobilecoin_client
        self.minimum_fee_pmob = mobilecoin_client.minimum_fee_pmob
        self.account_id = mobilecoin_client.account_id
        self.store = store
        self.signal = signal
        self.messenger = messenger
        self.logger = logging.getLogger("MOBot.Payments")
        self.timers = TimerFactory("Payments", self.logger)

    def _handle_payment_exception(self, e: Exception):
        if isinstance(e, ExceptionSendingReceipt):
            self.messenger.log_and_send_message(
                ChatStrings.COULD_NOT_GENERATE_RECEIPT,
            )
        elif isinstance(e, CustomerPaymentsAddressError):
            self.messenger.log_and_send_message(
                ChatStrings.PAYMENTS_DEACTIVATED.format(number=self.store.phone_number),
            )
        else:
            self.messenger.log_and_send_message(
                ChatStrings.PAYMENT_EXCEPTION
            )

    def get_minimum_fee_pmob(self) -> int:
        return self.mcc.minimum_fee_pmob

    @cached_property
    def minimum_fee_mob(self):
        return mc.pmob2mob(self.minimum_fee_pmob)

    @tenacity.retry(wait=tenacity.wait_random_exponential(min=1, max=30, multiplier=5))
    def get_payments_address(self, source: Union[dict, str]):
        if isinstance(source, dict):
            source = source["number"]
        else:
            source = str(source)

        self.logger.info(f"Getting payment address for customer {source}")
        customer_signal_profile = self.signal.get_profile(source)
        self.logger.info(f"Got customer({source}) signal profile {customer_signal_profile}")
        mobilecoin_address = customer_signal_profile.get('mobilecoin_address')
        if not mobilecoin_address:
            self.logger.warning(f"Found no MobileCoin payment address for {source}. Response: {customer_signal_profile}")
            raise CustomerPaymentsAddressError("Customer Payment address is none")
        return mobilecoin_address

    @tenacity.retry(wait=tenacity.wait_random_exponential(min=5, max=300, multiplier=2))
    def _send_mob_to_customer(self, customer: Customer, amount_mob: Decimal, cover_transaction_fee: bool, memo="Refund", batch: bool = False) -> Optional[Payment]:
        self.logger.info(f"Sending mob to customer: {customer}, amount: {amount_mob}")

        if not cover_transaction_fee:
            amount_mob = amount_mob - Decimal(mc.pmob2mob(self.minimum_fee_pmob))

        self.logger.info(f"Sending {amount_mob} MOB to {customer.phone_number}. Cover_transaction_fee: {cover_transaction_fee}")
        self.logger.info(f"Getting payment address for customer with # {customer.phone_number}")
        customer_payments_address = self.get_payments_address(customer.phone_number.as_e164)

        if amount_mob > 0:
            return self.send_mob_to_address(
                customer.phone_number.as_e164, amount_mob, customer_payments_address, memo=memo
            )

    def send_reply_payment(self, amount_mob: Decimal, cover_transaction_fee: bool, memo="Refund") -> Payment:
        with self.timers.get_timer("send_reply_payment"):
            ctx = ChatContext.get_current_context()
            self.logger.info(f"Sending reply payment to {ctx.customer}: {amount_mob} MOB...")

            try:
                payment = self._send_mob_to_customer(ctx.customer, amount_mob, cover_transaction_fee, memo)
                self.logger.debug(f"Payment logged: {amount_mob} MOB")
            except Exception as e:
                self.logger.exception(f"Failed sending reply payment to customer {ctx.customer}: {amount_mob} MOB")
                payment = Payment(
                    amount_mob=amount_mob,
                    status=PaymentStatus.Failure,
                    customer=ctx.customer,
                )
                self._handle_payment_exception(e)
            payment.save()
            self.logger.debug("Logging response object")
            MobotResponse.objects.create(
                incoming=ctx.message,
                outgoing_response=Message.objects.create(
                    direction=Direction.SENT,
                    status=MessageStatus.PROCESSED if payment.status == PaymentStatus.TransactionSuccess else MessageStatus.ERROR,
                    store=self.store,
                    customer=ctx.customer,
                    payment=payment,
                ),
            )
            return payment

    @tenacity.retry(wait=tenacity.wait_random_exponential(min=1, max=300, multiplier=5))
    def build_and_submit_transaction_with_proposal(self, amount_in_mob: Decimal,
                                                   customer_payments_address: str) -> (str, dict):
        self.logger.info(f"Building and submitting with proposal: {amount_in_mob} -> {customer_payments_address}")
        try:
            transaction_log, tx_proposal = self.mcc.build_and_submit_transaction_with_proposal(self.account_id,
                                                                                           amount=amount_in_mob,
                                                                                           to_address=customer_payments_address)
        except Exception as e:
            self.logger.exception("Exception when building transaction!")
            raise e
        list_of_txos = transaction_log["output_txos"]

        if len(list_of_txos) > 1:
            raise ValueError("Found more than one txout for this chat bot-initiated transaction.")

        txo_id = list_of_txos[0]["txo_id_hex"]
        if not isinstance(txo_id, str):
            raise Exception(f"TXO ID not a string: {txo_id}")
        return txo_id, tx_proposal

    @tenacity.retry(wait=tenacity.wait_random_exponential(min=1, max=60, multiplier=5))
    def get_txo_result(self, txo_id):
        """Smaller method for getting TXO result, with retry"""
        try:
            with self.timers.get_timer("get_txo"):
                self.mcc.get_txo(txo_id)
        except Exception as e:
            self.logger.exception("TxOut did not land yet, id: " + txo_id)
            raise e

    @tenacity.retry(wait=tenacity.wait_random_exponential(min=1, max=300, multiplier=5))
    def send_mob_to_address(self, source, amount_in_mob: Decimal, customer_payments_address: str, memo="Refund") -> Payment:
        """Attempt to send MOB to customer; retry if we fail."""
        # customer_payments_address is b64 encoded, but full service wants a b58 address
        ctx = ChatContext.get_current_context()
        customer_payments_address = mc.b64_public_address_to_b58_wrapper(
            customer_payments_address
        )

        with self.timers.get_timer("build_and_send_transaction"):
            self.logger.info(f"Sending {amount_in_mob} MOB to {customer_payments_address}")
            txo_id, tx_proposal = self.build_and_submit_transaction_with_proposal(
                amount_in_mob, customer_payments_address
            )
            self.logger.info(f"TXO_ID: {txo_id}")
            payment = Payment(
                amount_mob=amount_in_mob,
                txo_id=txo_id,
                customer=ctx.customer,
            )
            try:
                txo = self.get_txo_result(txo_id)
            except Exception as e:
                self.logger.exception(f"Exception getting TXO result for {txo_id}")
            else:
                try:
                    receipt = self.send_payment_receipt(source, tx_proposal, memo)
                    signal_payment = SignalPayment.objects.create(
                        note=memo,
                        receipt=receipt
                    )
                    payment.signal_payment = signal_payment
                    payment.status = PaymentStatus.TransactionSuccess
                except Exception as e:
                    self.logger.exception("Exception sending receipt")
                    raise ExceptionSendingReceipt(str(e))
                else:
                    return payment

    @tenacity.retry(wait=tenacity.wait_random_exponential(min=1, max=30, multiplier=2))
    def send_payment_receipt(self, source: str, tx_proposal: dict, memo="Refund") -> str:
        receiver_receipt_fs = self.create_receiver_receipt(tx_proposal)
        confirmation = receiver_receipt_fs["confirmation"]
        self.logger.info(f"Sending payment receipt to {source}")

        receiver_receipt = mc.full_service_receipt_to_b64_receipt(
            receiver_receipt_fs
        )
        resp = self.signal.send_payment_receipt(source, receiver_receipt, memo)
        self.logger.info(f"Send receipt {receiver_receipt} to {source}: {resp}")
        return receiver_receipt

    @tenacity.retry(wait=tenacity.wait_random_exponential(min=1, max=15, multiplier=2))
    def create_receiver_receipt(self, tx_proposal: dict):
        receiver_receipts = self.mcc.create_receiver_receipts(tx_proposal)
        # I'm assuming there will only be one receiver receipt (not including change tx out).
        if len(receiver_receipts) > 1:
            raise ValueError(
                "Found more than one txout for this chat bot-initiated transaction."
            )
        return receiver_receipts[0]

    def get_unspent_pmob(self) -> int:
        account_amount_response = self.mcc.get_balance_for_account(self.account_id)
        unspent_pmob = int(account_amount_response["unspent_pmob"])
        return unspent_pmob

    def has_enough_funds_for_payment(self, payment_amount: Decimal) -> bool:
        """Return a bool to check if we can pay out the desired amount"""
        return self.get_unspent_pmob() >= (
                mc.mob2pmob(payment_amount) + int(self.minimum_fee_pmob)
        )

    def get_minimum_fee_pmob(self) -> int:
        return self.mcc.minimum_fee_pmob

    def handle_not_enough_paid(self, amount_paid_mob: Decimal, drop_session: DropSession):
        customer = drop_session.customer
        item_price = drop_session.drop.item.price_in_mob
        self.logger.warning(f"Customer {customer} payment of {amount_paid_mob} not enough for item price {item_price}")

        refund_amount = mc.pmob2mob(mc.mob2pmob(amount_paid_mob) - self.minimum_fee_pmob)

        if refund_amount > 0:
            self.logger.warning("Refunding customer their payment minus transaction fees")
            self.messenger.log_and_send_message(
                ChatStrings.NOT_ENOUGH_REFUND.format(amount_paid=refund_amount.normalize())
            )
            self.send_reply_payment(amount_paid_mob, False)
        else:
            self.logger.warning("Not Refunding. Payment not enough to cover transaction fees for refund.")
            self.messenger.log_and_send_message(
                ChatStrings.NOT_ENOUGH
            )

    def handle_excess_payment(self, amount_paid_mob: Decimal, drop_session: DropSession):
        item_cost_mob = drop_session.drop.item.price_in_mob
        excess = amount_paid_mob - item_cost_mob
        net_excess = mc.pmob2mob(mc.mob2pmob(excess) - self.minimum_fee_pmob)
        self.messenger.log_and_send_message(
            ChatStrings.EXCESS_PAYMENT.format(refund=net_excess.normalize())
        )
        self.send_reply_payment(excess, False)

    def handle_payment_successful(self, amount_paid_mob: Decimal, drop_session: DropSession):
        customer = drop_session.customer
        self.messenger.log_and_send_message(
            ChatStrings.WE_RECEIVED_MOB.format(mob=amount_paid_mob.normalize())
        )

    def handle_out_of_stock(self, drop_session: DropSession):
        self.messenger.log_and_send_message(
            ChatStrings.OUT_OF_STOCK_REFUND
        )
        self.send_reply_payment(drop_session.drop.item.price_in_mob, True)

        drop_session.state = SessionState.REFUNDED
        drop_session.save()

    def process_signal_payment(self, message: Message) -> Payment:
        return self.mcc.process_signal_payment(message)

    def handle_item_payment(self, amount_paid_mob: Decimal, drop_session: DropSession):
        item_cost_mob = drop_session.drop.item.price_in_mob
        if amount_paid_mob < item_cost_mob:
            self.handle_not_enough_paid(amount_paid_mob, drop_session)
        elif amount_paid_mob > (item_cost_mob + mc.pmob2mob(self.minimum_fee_pmob)):
            self.handle_excess_payment(amount_paid_mob, drop_session)
        else:
            self.handle_payment_successful(amount_paid_mob, drop_session)

        skus = drop_session.drop.item.skus.order_by("sort_order")

        if skus.count() == 0:
            self.handle_out_of_stock(drop_session)
        else:
            return True
        return False