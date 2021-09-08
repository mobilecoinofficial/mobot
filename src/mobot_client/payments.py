# Copyright (c) 2021 MobileCoin. All rights reserved.

import time
from decimal import Decimal
import threading
import logging

import mobilecoin as mc
from django.utils import timezone

from mobot_client.models import (
    SessionState,
    Store,
    DropSession,
)


from mobot_client.chat_strings import ChatStrings
from mobot_client.utils import TimerFactory


class NotEnoughFundsException(Exception):
    pass


class Payments:
    """The Payments class handles the logic relevant to sending MOB and handling receipts."""

    def __init__(
            self, mobilecoin_client, minimum_fee_pmob, account_id, store: Store, messenger, signal
    ):
        self.mcc = mobilecoin_client
        self.minimum_fee_pmob = minimum_fee_pmob
        self.account_id = account_id
        self.store = store
        self.signal = signal
        self.messenger = messenger
        self.logger = logging.getLogger("MOBot.Payments")
        self._transaction_lock = threading.Lock()
        self.timers = TimerFactory("Payments", self.logger)

    def get_payments_address(self, source):
        if isinstance(source, dict):
            source = source["number"]

        self.logger.info(f"Getting payment address for customer {source}")
        customer_signal_profile = self.signal.get_profile(source, True)
        self.logger.info(f"Got customer({source}) signal profile {customer_signal_profile}")
        mobilecoin_address = customer_signal_profile.get('mobilecoin_address')
        if not mobilecoin_address:
            self.logger.warning(f"Found no MobileCoin payment address for {source.number}. Response: {customer_signal_profile}")
        return mobilecoin_address

    def send_mob_to_customer(self, customer, source, amount_mob, cover_transaction_fee):
        with self.timers.get_timer("send_mob_to_customer") as ctx:
            if isinstance(source, dict):
                source = source["number"]

            if not cover_transaction_fee:
                amount_mob = amount_mob - Decimal(mc.pmob2mob(self.minimum_fee_pmob))

            self.logger.info(f"Sending {amount_mob} MOB to {source}. Cover_transaction_fee: {cover_transaction_fee}")

            customer_payments_address = self.get_payments_address(source)
            if customer_payments_address is None:
                self.messenger.log_and_send_message(
                    customer,
                    source,
                    ChatStrings.PAYMENTS_DEACTIVATED.format(number=self.store.phone_number),
                )
            elif amount_mob > 0:
                self.send_mob_to_address(
                    source, self.account_id, amount_mob, customer_payments_address
                )

    def send_mob_to_address(self, source, account_id: str, amount_in_mob: Decimal, customer_payments_address: str):
        with self.timers.get_timer("send_mob_to_address"):
        # customer_payments_address is b64 encoded, but full service wants a b58 address
            self.logger.info(f"Sending {amount_in_mob} MOB to {source}")
            customer_payments_address = mc.utility.b64_public_address_to_b58_wrapper(
                customer_payments_address
            )
            with self.timers.get_timer("acquire_payment_lock"):
                self._transaction_lock.acquire(blocking=True)
                tx_proposal = self.mcc.build_transaction(
                    account_id, amount_in_mob, customer_payments_address
                )
                txo_id = self.submit_transaction(tx_proposal, account_id)
                self._transaction_lock.release()

            with self.timers.get_timer("allow_transaction_to_land"):
                for _ in range(10):
                    try:
                        with self.timers.get_timer("get_txo"):
                            self.mcc.get_txo(txo_id)
                    except Exception:
                        self.logger.exception(f"TxOut did not land yet, id: {txo_id}")
                    else:
                        self.send_payment_receipt(source, tx_proposal)
                        return
                    self.logger.warning(f"Did not get TXO for {txo_id}. Sleeping!")
                    time.sleep(1.0)
                else:
                    self.signal.send_message(
                        source,
                        ChatStrings.COULD_NOT_GENERATE_RECEIPT,
                    )

    def submit_transaction(self, tx_proposal: dict, account_id: str):
        # retry up to 10 times in case there's some failure with a 1 sec timeout in between each
        with self.timers.get_timer("submit_transaction"):
            transaction_log = self.mcc.submit_transaction(tx_proposal, account_id)
            list_of_txos = transaction_log["output_txos"]

            if len(list_of_txos) > 1:
                raise ValueError("Found more than one txout for this chat bot-initiated transaction.")

            return list_of_txos[0]["txo_id_hex"]

    def send_payment_receipt(self, source: str, tx_proposal: dict):
        with self.timers.get_timer("send_payment_receipt"):
            receiver_receipt = self.create_receiver_receipt(tx_proposal)
            receiver_receipt = mc.utility.full_service_receipt_to_b64_receipt(
                receiver_receipt
            )
            resp = self.signal.send_payment_receipt(source, receiver_receipt, "Refund")
            self.logger.info(f"Send receipt {receiver_receipt} to {source}: {resp}")

    def create_receiver_receipt(self, tx_proposal: dict):
        with self.timers.get_timer("create_receiver_receipt"):
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

    def has_enough_funds_for_payment(self, payment_amount: int) -> bool:
        """Return a bool to check if we can pay out the desired amount"""
        return self.get_unspent_pmob() >= (
                payment_amount + int(self.get_minimum_fee_pmob())
        )

    def get_minimum_fee_pmob(self) -> int:
        return self.minimum_fee_pmob

    def handle_not_enough_paid(self, amount_paid_mob: Decimal, drop_session: DropSession):
        with self.timers.get_timer("handle_not_enough_paid"):
            customer = drop_session.customer
            source = drop_session.customer.phone_number.as_e164
            item_price = drop_session.drop.item.price_in_mob
            self.logger.warning(f"Customer {customer} payment of {amount_paid_mob} not enough for item price {item_price}")

            refund_amount = mc.pmob2mob(mc.mob2pmob(amount_paid_mob) - self.minimum_fee_pmob)

            if refund_amount > 0:
                self.logger.warning("Refunding customer their payment minus transaction fees")
                self.messenger.log_and_send_message(
                    customer,
                    source,
                    ChatStrings.NOT_ENOUGH_REFUND.format(amount_paid=refund_amount.normalize())
                )
                self.send_mob_to_customer(customer, source, amount_paid_mob, False)
            else:
                self.logger.warning("Not Refunding. Payment not enough to cover transaction fees for refund.")
                self.messenger.log_and_send_message(
                    customer,
                    source,
                    ChatStrings.NOT_ENOUGH
                )

    def handle_excess_payment(self, amount_paid_mob: Decimal, drop_session: DropSession):
        self.logger.info(f"Handling excess payment from {drop_session.customer}")
        item_cost_mob = drop_session.drop.item.price_in_mob
        excess = amount_paid_mob - item_cost_mob
        net_excess = mc.pmob2mob(mc.mob2pmob(excess) - self.minimum_fee_pmob)
        self.messenger.log_and_send_message(
            drop_session.customer,
            drop_session.customer.phone_number.as_e164,
            ChatStrings.EXCESS_PAYMENT.format(refund=net_excess.normalize())
        )
        self.send_mob_to_customer(drop_session.customer, drop_session.customer.phone_number.as_e164, excess, False)

    def handle_payment_successful(self, amount_paid_mob: Decimal, drop_session: DropSession):
        self.logger.info(f"Handling payment successful from {drop_session.customer}")
        customer = drop_session.customer
        self.messenger.log_and_send_message(
            customer,
            customer.phone_number.as_e164,
            ChatStrings.WE_RECEIVED_MOB.format(mob=amount_paid_mob.normalize())
        )

    def handle_out_of_stock(self, amount_paid_mob: Decimal, drop_session: DropSession):
        self.logger.info(f"Handling out of stock from {drop_session.customer}")
        self.messenger.log_and_send_message(
            drop_session.customer,
            drop_session.customer.phone_number.as_e164,
            ChatStrings.OUT_OF_STOCK_REFUND
        )
        self.send_mob_to_customer(drop_session.customer,
                                  drop_session.customer.phone_number.as_e164,
                                  drop_session.drop.item.price_in_mob,
                                  True)

        drop_session.state = SessionState.REFUNDED
        drop_session.save()

    def handle_item_payment(self, amount_paid_mob: Decimal, drop_session: DropSession):
        with self.timers.get_timer("handle_item_payment"):
            item_cost_mob = drop_session.drop.item.price_in_mob
            if amount_paid_mob < item_cost_mob:
                self.handle_not_enough_paid(amount_paid_mob, drop_session)
            elif (
                    mc.mob2pmob(amount_paid_mob)
                    > mc.mob2pmob(item_cost_mob) + self.minimum_fee_pmob
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
