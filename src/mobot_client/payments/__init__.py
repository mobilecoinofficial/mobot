# Copyright (c) 2021 MobileCoin. All rights reserved.
import mobilecoin
import mobilecoin as mc
import time
from decimal import Decimal


from mobot_client.drop_session import ItemSessionState
from mobot_client.models import (
    Order,
    Sku,
    Store,
)
from mobot_client.logger import SignalMessenger
from signald_client import Signal
from mobot_client.chat_strings import ChatStrings


class Payments:
    """The Payments class handles the logic relevant to sending MOB and handling receipts."""

    def __init__(
            self, mobilecoin_client: mobilecoin.Client, minimum_fee_pmob: int, account_id: str, store: Store, messenger: SignalMessenger, signal: Signal
    ):
        self.mcc = mobilecoin_client
        self.minimum_fee_pmob = minimum_fee_pmob
        self.account_id = account_id
        self.store = (store,)
        self.signal = signal
        self.messenger = messenger

    def get_payments_address(self, source):
        if isinstance(source, dict):
            source = source["number"]

        customer_signal_profile = self.signal.get_profile(source, True)
        print(customer_signal_profile)
        return customer_signal_profile.get("mobilecoin_address")

    def send_mob_to_customer(self, customer, source, amount_mob, cover_transaction_fee):
        if isinstance(source, dict):
            source = source["number"]

        customer_payments_address = self.get_payments_address(source)
        if customer_payments_address is None:
            self.messenger.log_and_send_message(
                customer,
                source,
                ChatStrings.PAYMENTS_DEACTIVATED.format(number=self.store.phone_number),
            )
            return

        if not cover_transaction_fee:
            amount_mob = amount_mob - Decimal(mc.pmob2mob(self.minimum_fee_pmob))
        else:
            amount_mob = amount_mob + Decimal(mc.pmob2mob(self.minimum_fee_pmob))

        if amount_mob <= 0:
            return

        self.send_mob_to_address(
            source, self.account_id, amount_mob, customer_payments_address
        )

    def send_mob_to_address(
            self, source, account_id, amount_in_mob, customer_payments_address
    ):
        # customer_payments_address is b64 encoded, but full service wants a b58 address
        customer_payments_address = mc.utility.b64_public_address_to_b58_wrapper(
            customer_payments_address
        )

        tx_proposal = self.mcc.build_transaction(
            account_id, amount_in_mob, customer_payments_address
        )
        txo_id = self.submit_transaction(tx_proposal, account_id)
        for _ in range(10):
            try:
                self.mcc.get_txo(txo_id)
                break
            except Exception:
                print("TxOut did not land yet, id: " + txo_id)
                pass
            time.sleep(1.0)
        else:
            self.signal.send_message(
                source,
                "couldn't generate a receipt, please contact us if you didn't a payment!",
            )
            return

        self.send_payment_receipt(source, tx_proposal)

    def submit_transaction(self, tx_proposal, account_id):
        # retry up to 10 times in case there's some failure with a 1 sec timeout in between each
        transaction_log = self.mcc.submit_transaction(tx_proposal, account_id)
        list_of_txos = transaction_log["output_txos"]

        if len(list_of_txos) > 1:
            raise ValueError(
                "Found more than one txout for this chat bot-initiated transaction."
            )

        return list_of_txos[0]["txo_id_hex"]

    def send_payment_receipt(self, source, tx_proposal):
        receiver_receipt = self.create_receiver_receipt(tx_proposal)
        receiver_receipt = mc.utility.full_service_receipt_to_b64_receipt(
            receiver_receipt
        )
        resp = self.signal.send_payment_receipt(source, receiver_receipt, "Refund")
        print("Send receipt", receiver_receipt, "to", source, ":", resp)

    def create_receiver_receipt(self, tx_proposal):
        receiver_receipts = self.mcc.create_receiver_receipts(tx_proposal)
        # I'm assuming there will only be one receiver receipt (not including change tx out).
        if len(receiver_receipts) > 1:
            raise ValueError(
                "Found more than one txout for this chat bot-initiated transaction."
            )
        return receiver_receipts[0]

    def get_unspent_pmob(self):
        account_amount_response = self.mcc.get_balance_for_account(self.account_id)
        unspent_pmob = int(account_amount_response["unspent_pmob"])
        return unspent_pmob

    def get_minimum_fee_pmob(self):
        return self.minimum_fee_pmob

    def handle_item_payment(self, source, customer, amount_paid_mob, drop_session):
        item_cost_mob = mc.pmob2mob(drop_session.drop.item.price_in_pmob)

        if amount_paid_mob < item_cost_mob:
            refund_amount = mc.pmob2mob(
                mc.mob2pmob(amount_paid_mob) - self.minimum_fee_pmob
            )
            if refund_amount > 0:
                self.messenger.log_and_send_message(
                    customer,
                    source,
                    ChatStrings.NOT_ENOUGH_REFUND.format(amount_paid=refund_amount.normalize())
                )
                self.send_mob_to_customer(customer, source, amount_paid_mob, False)
            else:
                self.messenger.log_and_send_message(
                    customer,
                    source,
                    ChatStrings.NOT_ENOUGH
                )
            return

        if (
                mc.mob2pmob(amount_paid_mob)
                > mc.mob2pmob(item_cost_mob) + self.minimum_fee_pmob
        ):
            excess = amount_paid_mob - item_cost_mob
            net_excess = mc.pmob2mob(mc.mob2pmob(excess) - self.minimum_fee_pmob)
            self.messenger.log_and_send_message(
                customer,
                source,
                ChatStrings.EXCESS_PAYMENT.format(refund=net_excess.normalize())
            )
            self.send_mob_to_customer(customer, source, excess, False)
        else:
            self.messenger.log_and_send_message(
                customer,
                source,
                f"We received {amount_paid_mob.normalize()} MOB"
            )

        available_options = []
        skus = Sku.objects.filter(item=drop_session.drop.item).order_by("sort_order")

        for sku in skus:
            number_ordered = Order.objects.filter(sku=sku).count()
            if number_ordered < sku.quantity:
                available_options.append(sku)

        if len(available_options) == 0:
            self.messenger.log_and_send_message(
                customer,
                source,
                ChatStrings.OUT_OF_STOCK_REFUND
            )
            self.send_mob_to_customer(customer, source, item_cost_mob, True)
            drop_session.state = ItemSessionState.REFUNDED.value
            drop_session.save()
            return

        message_to_send = (
            ChatStrings.WAITING_FOR_SIZE_PREFIX + ChatStrings.get_options(available_options, capitalize=True)
        )

        self.messenger.log_and_send_message(customer, source, message_to_send)
        drop_session.state = ItemSessionState.WAITING_FOR_SIZE.value
        drop_session.save()

        return