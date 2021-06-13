import logging
import os
import time
import pytz

from django.utils import timezone
from django.core.management.base import BaseCommand
from mobot.apps.signald_client import Signal
from mobot.apps.merchant_services.models import MCStore, Customer, DropSession, Drop, CustomerStorePreferences, Message, Merchant
import mobilecoin as mc
from decimal import Decimal
from django.conf import settings
from logging import getLogger
import sys

SIGNALD_ADDRESS = settings.SIGNALD_ADDRESS
SIGNALD_PORT = settings.SIGNALD_PORT
STORE_NUMBER = settings.STORE_NUMBER
signal = Signal(STORE_NUMBER, socket_path=(SIGNALD_ADDRESS, int(SIGNALD_PORT)))

FULLSERVICE_ADDRESS = settings.FULLSERVICE_ADDRESS
FULLSERVICE_PORT = settings.FULLSERVICE_PORT
FULLSERVICE_URL = f"http://{FULLSERVICE_ADDRESS}:{FULLSERVICE_PORT}/wallet"
mcc = mc.Client(url=FULLSERVICE_URL)
logger = getLogger(__file__)
signal = Signal(settings.STORE_NUMBER, socket_path=(settings.SIGNALD_ADDRESS, int(settings.SIGNALD_PORT)))

mcc = mc.Client(url=settings.FULLSERVICE_URL)
stores = MCStore.objects.all()
logging.info(stores)
while True:
    try:
        store = MCStore.objects.get(id=settings.STORE_NUMBER)
        merchant = Merchant.objects.get(phone_number=store.merchant_ref.phone_number)
        break
    except MCStore.DoesNotExist:
        logger.debug(f"Store does not exist yet with number {settings.STORE_NUMBER}")
        time.sleep(10000)



SESSION_STATE_COMPLETED = -1
SESSION_STATE_STARTED = 0
SESSION_STATE_ALLOW_CONTACT_REQUESTED = 1

MESSAGE_DIRECTION_RECEIVED = 0
MESSAGE_DIRECTION_SENT = 1

signal.set_profile("MOBot", settings.STORE_ADDRESS, None, False)


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


def get_payments_address(source):
    customer_signal_profile = signal.get_profile(source, True)
    customer_payments_address = customer_signal_profile['data']['paymentsAddress']
    if customer_payments_address is None:
        return None
    return customer_payments_address


def refund_customer(source, amount_mob, cover_transaction_fee):
    customer_payments_address = get_payments_address(source)
    if customer_payments_address is None:
        signal.send_message(source,
                            ("We have a refund for you, but your payments have been deactivated\n\n"
                             "Please contact customer service at {}").format(settings.STORE_NUMBER))
        return

    if not cover_transaction_fee:
        amount_mob = amount_mob - Decimal(0.01)

    if amount_mob <= 0:
        signal.send_message(source,
                            "Sorry. Can't issue a refund because the refund amount is less than the transaction fee 🙁")
        return

    send_mob_to_user(source, settings.ACCOUNT_ID, amount_mob, customer_payments_address)


def send_mob_to_user(source, account_id, amount_in_mob, customer_payments_address):
    tx_proposal = mcc.build_transaction(account_id, amount_in_mob, customer_payments_address)
    txo_id = submit_transaction(tx_proposal, account_id)
    for _ in range(10):
        try:
            mcc.get_txo(txo_id)
            break
        except Exception:
            print("TxOut did not land yet, id: " + txo_id)
            pass
        time.sleep(1.0)
    else:
        signal.send_message(source, "couldn't generate a receipt, please contact us if you didn't get a refund!")
        return

    send_payment_receipt(source, tx_proposal)
    signal.send_message(source, "{} MOB refunded".format(float(amount_in_mob)))


def submit_transaction(tx_proposal, account_id):
    transaction_log = mcc.submit_transaction(tx_proposal, account_id)
    list_of_txos = transaction_log["output_txos"]

    # I'm assuming there will only be one tx out (not including change tx out).
    if len(list_of_txos) > 1:
        raise ValueError("Found more than one txout for this chat bot-initiated transaction.")

    return list_of_txos[0]["txo_id_hex"]


def send_payment_receipt(source, tx_proposal):
    receiver_receipt = create_receiver_receipt(tx_proposal)
    print("sending payment receipt")
    print(receiver_receipt)
    signal.send_payment_receipt(source, receiver_receipt, "Refund")


def create_receiver_receipt(tx_proposal):
    receiver_receipts = mcc.create_receiver_receipts(tx_proposal)
    # I'm assuming there will only be one receiver receipt (not including change tx out).
    if len(receiver_receipts) > 1:
        raise ValueError("Found more than one txout for this chat bot-initiated transaction.")
    return receiver_receipts[0]



def log_and_send_message(customer, source, text):
    sent_message = Message(customer=customer, store=store, text=text, direction=MESSAGE_DIRECTION_SENT)
    sent_message.save()
    signal.send_message(source, text)


def get_signal_profile_name(source):
    customer_signal_profile = signal.get_profile(source, True)
    try:
        customer_name = customer_signal_profile['data']['name']
        return customer_name
    except:
        return None


def get_payments_address(source):
    customer_signal_profile = signal.get_profile(source, True)
    print(customer_signal_profile)
    try:
        customer_payments_address = customer_signal_profile['data']['paymentsAddress']
        return customer_payments_address
    except:
        return None


class Command(BaseCommand):
    help = 'Run MOBot Client'

    def handle(self, *args, **kwargs):
        try:
            signal.run_chat(True)
        except KeyboardInterrupt as e:
            print()
            pass