# Copyright (c) 2021 MobileCoin. All rights reserved.

import time
from decimal import Decimal
import logging
from typing import Optional

import mc_util as mc
from signald import Signal

from mobot_client.logger import SignalMessenger
from mobot_client.models import (
    SessionState,
    Store,
    DropSession,
)
from mobot_client.models.messages import (
    Payment,
    MobotResponse, Direction, SignalPayment, PaymentStatus, Message, MessageStatus,
)
from mobot_client.chat_strings import ChatStrings
from mobot_client.payments.client import MCClient
from mobot_client.utils import TimerFactory
from mobot_client.core.context import get_current_context


class NotEnoughFundsException(Exception):
    pass


class PaymentException(Exception):
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
        with self.timers.get_timer("Startup"):
            self.logger.info("Payments started")

    def get_minimum_fee_pmob(self) -> int:
        return self.mcc.minimum_fee_pmob

    def get_payments_address(self, source):
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
        return mobilecoin_address

    def _send_mob_to_customer(self, customer, amount_mob, cover_transaction_fee, memo="Refund") -> Optional[Payment]:
        self.logger.info(f"Sending mob to customer: {customer}, amount: {amount_mob}")
        with self.timers.get_timer("send_mob_to_customer"):
            source = customer.phone_number.as_e164

            if not cover_transaction_fee:
                amount_mob = amount_mob - Decimal(mc.pmob2mob(self.minimum_fee_pmob))
            else:
                # covering transaction fee includes reimbursing the user for the transaction
                # fee that they spent sending us the original transaction that we are refunding
                amount_mob = amount_mob + Decimal(mc.pmob2mob(self.minimum_fee_pmob))

            self.logger.info(f"Sending {amount_mob} MOB to {source}. Cover_transaction_fee: {cover_transaction_fee}")
            self.logger.info(f"Getting payment address for customer with # {source}")
            customer_payments_address = self.get_payments_address(source)

            if customer_payments_address is None:
                self.messenger.log_and_send_message(
                    ChatStrings.PAYMENTS_DEACTIVATED.format(number=self.store.phone_number),
                )
            elif amount_mob > 0:
                return self.send_mob_to_address(
                    source, self.account_id, amount_mob, customer_payments_address, memo=memo
                )

    def send_reply_payment(self, amount_mob, cover_transaction_fee, memo="Refund"):
        ctx = get_current_context()
        self.logger.info(f"Sending reply payment to {ctx.customer}: {amount_mob} MOB...")

        try:
            payment = self._send_mob_to_customer(ctx.message.customer, amount_mob, cover_transaction_fee, memo)
            self.logger.info("Payment logged!")
        except Exception:
            self.logger.exception(f"Failed sending reply payment to customer {ctx.customer}: {amount_mob} MOB")
            payment = Payment(
                amount_mob=amount_mob,
                status=PaymentStatus.Failure,
                customer=ctx.customer,
            )
        payment.save()
        response = MobotResponse.objects.create(
            incoming=ctx.message,
            outgoing_response=Message.objects.create(
                direction=Direction.SENT,
                status=MessageStatus.PROCESSED if payment.status == PaymentStatus.TransactionSuccess else MessageStatus.ERROR,
                store=self.store,
                customer=ctx.customer,
                payment=payment,
            ),
        )

    def build_and_submit_transaction_with_proposal(self, account_id: str, amount_in_mob: Decimal,
                                                   customer_payments_address: str) -> (str, dict):
        self.logger.info("Building and submitting with proposal")
        with self.timers.get_timer("submit_transaction"):
            transaction_log, tx_proposal = self.mcc.build_and_submit_transaction_with_proposal(account_id,
                                                                                               amount=amount_in_mob,
                                                                                               to_address=customer_payments_address)
            list_of_txos = transaction_log["output_txos"]

            if len(list_of_txos) > 1:
                raise ValueError("Found more than one txout for this chat bot-initiated transaction.")

            txo_id = list_of_txos[0]["txo_id_hex"]
            if not isinstance(txo_id, str):
                raise Exception(f"TXO ID not a string: {txo_id}")
            return txo_id, tx_proposal

    def get_minimum_fee_pmob(self) -> int:
        return self.mcc.minimum_fee_pmob

    def send_mob_to_address(self, source, account_id: str, amount_in_mob: Decimal, customer_payments_address: str, memo="Refund") -> Payment:
        # customer_payments_address is b64 encoded, but full service wants a b58 address
        ctx = get_current_context()
        customer_payments_address = mc.b64_public_address_to_b58_wrapper(
            customer_payments_address
        )

        with self.timers.get_timer("build_and_send_transaction"):
            self.logger.info(f"Sending {amount_in_mob} MOB to {customer_payments_address}")
            txo_id, tx_proposal = self.build_and_submit_transaction_with_proposal(
                account_id, amount_in_mob, customer_payments_address
            )
            self.logger.info(f"TXO_ID: {txo_id}")
            payment = Payment(
                amount_mob=amount_in_mob,
                txo_id=txo_id,
                customer=ctx.customer,
            )

        for _ in range(10):
            try:
                with self.timers.get_timer("get_txo"):
                    self.mcc.get_txo(txo_id)
            except Exception:
                print("TxOut did not land yet, id: " + txo_id)
            else:
                receipt = self.send_payment_receipt(source, tx_proposal, memo)
                signal_payment = SignalPayment.objects.create(
                    note=memo,
                    receipt=receipt
                )
                payment.signal_payment = signal_payment
                payment.status = PaymentStatus.TransactionSuccess
                return payment
            time.sleep(1.0)
        else:
            self.messenger.log_and_send_message(
                ChatStrings.COULD_NOT_GENERATE_RECEIPT,
            )
        return payment

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

    def create_receiver_receipt(self, tx_proposal: dict):
        receiver_receipts = self.mcc.create_receiver_receipts(tx_proposal)
        # I'm assuming there will only be one receiver receipt (not including change tx out).
        if len(receiver_receipts) > 1:
            raise ValueError(
                "Found more than one txout for this chat bot-initiated transaction."
            )
        return receiver_receipts[0]

    def get_unspent_pmob(self) -> int:
        with self.timers.get_timer("get_unspent_pmob"):
            account_amount_response = self.mcc.get_balance_for_account(self.account_id)
            unspent_pmob = int(account_amount_response["unspent_pmob"])
            return unspent_pmob

    def has_enough_funds_for_payment(self, payment_amount: Decimal) -> bool:
        """Return a bool to check if we can pay out the desired amount"""
        return self.get_unspent_pmob() >= (
                mc.mob2pmob(payment_amount) + int(self.minimum_fee_pmob)
        )

    def handle_not_enough_paid(self, amount_paid_mob: Decimal, drop_session: DropSession):
        customer = drop_session.customer
        source = drop_session.customer.phone_number.as_e164
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

    def handle_out_of_stock(self, amount_paid_mob: Decimal, drop_session: DropSession):
        self.messenger.log_and_send_message(
            ChatStrings.OUT_OF_STOCK_REFUND
        )
        self.send_reply_payment(drop_session.drop.item.price_in_mob, True)

        drop_session.state = SessionState.REFUNDED
        drop_session.save()

    def handle_item_payment(self, amount_paid_mob: Decimal, drop_session: DropSession):
        item_cost_mob = drop_session.drop.item.price_in_mob
        if amount_paid_mob < item_cost_mob:
            self.handle_not_enough_paid(amount_paid_mob, drop_session)
        elif (
                amount_paid_mob
                > item_cost_mob + mc.pmob2mob(self.minimum_fee_pmob)
        ):
            self.handle_excess_payment(amount_paid_mob, drop_session)
        else:
            self.handle_payment_successful(amount_paid_mob, drop_session)

        skus = drop_session.drop.item.skus.order_by("sort_order")

        if skus.count() == 0:
            self.handle_out_of_stock(amount_paid_mob, drop_session)
        else:
            return True
        return False
