from datetime import tzinfo
import os
import time
import pytz
import random

from django.utils import timezone
from django.core.management.base import BaseCommand
from signald_client import Signal
from mobot_client.models import Store, Customer, DropSession, Drop, CustomerStorePreferences, Message, BonusCoin
import mobilecoin as mc
from decimal import Decimal

SIGNALD_ADDRESS = os.getenv("SIGNALD_ADDRESS", "127.0.0.1")
SIGNALD_PORT = os.getenv("SIGNALD_PORT", "15432")
STORE_NUMBER = os.environ["STORE_NUMBER"]
signal = Signal(STORE_NUMBER, socket_path=(SIGNALD_ADDRESS, int(SIGNALD_PORT)))

FULLSERVICE_ADDRESS = os.getenv("FULLSERVICE_ADDRESS", "127.0.0.1")
FULLSERVICE_PORT = os.getenv("FULLSERVICE_PORT", "9090")
FULLSERVICE_URL = f"http://{FULLSERVICE_ADDRESS}:{FULLSERVICE_PORT}/wallet"
mcc = mc.Client(url=FULLSERVICE_URL)

store = Store.objects.get(phone_number=STORE_NUMBER)

all_accounts_response = mcc.get_all_accounts()
ACCOUNT_ID = next(iter(all_accounts_response))
account_obj = all_accounts_response[ACCOUNT_ID]
PUBLIC_ADDRESS = account_obj['main_address']

get_network_status_response = mcc.get_network_status()
MINIMUM_FEE_PMOB = get_network_status_response['fee_pmob']

SESSION_STATE_CANCELLED = -1
SESSION_STATE_READY_TO_RECEIVE_INITIAL = 0
SESSION_STATE_WAITING_FOR_BONUS_TRANSACTION = 1
SESSION_STATE_ALLOW_CONTACT_REQUESTED = 2
SESSION_STATE_COMPLETED = 3

MESSAGE_DIRECTION_RECEIVED = 0
MESSAGE_DIRECTION_SENT = 1

signal.set_profile("MOBot", PUBLIC_ADDRESS, None, False)

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

def send_mob_to_customer(source, amount_mob, cover_transaction_fee):
    customer_payments_address = get_payments_address(source)
    if customer_payments_address is None:
        signal.send_message(source,
                       ("We have a refund for you, but your payments have been deactivated\n\n"
                       "Please contact customer service at {}").format(STORE_NUMBER))
        return

    if not cover_transaction_fee:
        amount_mob = amount_mob - Decimal(mc.pmob2mob(MINIMUM_FEE_PMOB))

    if amount_mob <= 0:
        signal.send_message(source, "Sorry. Can't issue a refund because the refund amount is less than the transaction fee 🙁")
        return

    send_mob_to_address(source, ACCOUNT_ID, amount_mob, customer_payments_address)

def send_mob_to_address(source, account_id, amount_in_mob, customer_payments_address):
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
        signal.send_message(source, "couldn't generate a receipt, please contact us if you didn't a payment!")
        return

    send_payment_receipt(source, tx_proposal)
    signal.send_message(source, "{} MOB sent".format(float(amount_in_mob)))

def submit_transaction(tx_proposal, account_id):
    # retry up to 10 times in case there's some failure with a 1 sec timeout in between each
    transaction_log = mcc.submit_transaction(tx_proposal, account_id)
    list_of_txos = transaction_log["output_txos"]

    if len(list_of_txos) > 1:
        raise ValueError("Found more than one txout for this chat bot-initiated transaction.")

    return list_of_txos[0]["txo_id_hex"]

def send_payment_receipt(source, tx_proposal):
    receiver_receipt = create_receiver_receipt(tx_proposal)
    signal.send_payment_receipt(source, receiver_receipt, "Refund")

def create_receiver_receipt(tx_proposal):
    receiver_receipts = mcc.create_receiver_receipts(tx_proposal)
    # I'm assuming there will only be one receiver receipt (not including change tx out).
    if len(receiver_receipts) > 1:
        raise ValueError("Found more than one txout for this chat bot-initiated transaction.")
    return receiver_receipts[0]

def under_drop_quota(drop):
    return True

def minimum_coin_available(drop):
    return True

def get_bonus_coin_amount(drop):
    return

@signal.payment_handler
def handle_payment(source, receipt):
    receipt_status = None
    transaction_status = "TransactionPending"

    while transaction_status == "TransactionPending":
        receipt_status = mcc.check_receiver_receipt_status(PUBLIC_ADDRESS, _signald_to_fullservice(receipt))
        transaction_status = receipt_status["receipt_transaction_status"]

    if transaction_status != "TransactionSuccess":
        return "The transaction failed!"

    amount_paid_mob = mc.pmob2mob(receipt_status["txo"]["value_pmob"])

    customer = None
    drop_session = None

    try:
        customer, _ = Customer.objects.get_or_create(phone_number=source['number'])
        drop_session = DropSession.objects.get(customer=customer, state=SESSION_STATE_WAITING_FOR_BONUS_TRANSACTION)
    except Exception as e:
        print(e)
        log_and_send_message(customer, source, "not expecting a payment, sending it back")
        send_mob_to_customer(source, amount_paid_mob, False)
        return

    bonus_coin_objects_for_drop = BonusCoin.objects.filter(drop=drop_session.drop)
    bonus_coins = []

    for bonus_coin in bonus_coin_objects_for_drop:
        number_claimed = DropSession.objects.filter(drop=drop_session.drop, bonus_coin_claimed=bonus_coin).count()
        number_remaining = bonus_coin.number_available - number_claimed
        bonus_coins.extend([bonus_coin] * number_remaining)

    if len(bonus_coins) == 0:
        log_and_send_message(customer, source, "out of bonus coins, sending you back your MOB")
        send_mob_to_customer(source, amount_paid_mob, True)
        return

    random_index = random.randint(0, len(bonus_coins) - 1)
    amount_in_mob = mc.pmob2mob(bonus_coins[random_index].amount_pmob)
    amount_to_send_mob = amount_in_mob + amount_paid_mob
    send_mob_to_customer(source, amount_to_send_mob, True)
    drop_session.bonus_coin_claimed = bonus_coins[random_index]
    drop_session.state = SESSION_STATE_ALLOW_CONTACT_REQUESTED
    drop_session.save()
    log_and_send_message(customer, source, "sending you some bonus mob!")
    return

def handle_drop_session_allow_contact_requested(message, drop_session):
    if message.text.lower() == "y" or message.text.lower() == "yes":
        customer_prefs = CustomerStorePreferences(customer=drop_session.customer, store=store, allows_contact=True)
        customer_prefs.save()
        drop_session.state = SESSION_STATE_COMPLETED
        drop_session.save()
        log_and_send_message(drop_session.customer, message.source, "Thanks! MOBot OUT. Buh-bye")
        return

    if message.text.lower() == "n" or message.text.lower() == "no":
        customer_prefs = CustomerStorePreferences(customer=drop_session.customer, store=store, allows_contact=False)
        customer_prefs.save()
        drop_session.state = SESSION_STATE_COMPLETED
        drop_session.save()
        log_and_send_message(drop_session.customer, message.source, "Thanks! MOBot OUT. Buh-bye")
        return

    if message.text.lower() == "p" or message.text.lower() == "privacy":
        log_and_send_message(drop_session.customer, message.source, "privacy policy")
        return

    if message.text.lower() == "help":
        log_and_send_message(drop_session.customer, message.source, "allow contact commands verbose")
        return

    log_and_send_message(drop_session.customer, message.source, "allow contact commands")

def handle_drop_session_ready_to_receive(message, drop_session):
    if message.text.lower() == "n" or message.text.lower() == "no" or message.text.lower() == "cancel":
        drop_session.state = SESSION_STATE_CANCELLED
        drop_session.save()
        log_and_send_message(drop_session.customer, message.source, "session cancelled, message us again when you're ready!")
        return

    if message.text.lower() == "y" or message.text.lower() == "yes":
        if not under_drop_quota(drop_session.drop):
            log_and_send_message(drop_session.customer, message.source, "over quota for drop!")
            drop_session.state = SESSION_STATE_COMPLETED
            drop_session.save()
            return

        if not minimum_coin_available(drop_session.drop):
            log_and_send_message(drop_session.customer, message.source, "no coin left!")
            drop_session.state = SESSION_STATE_COMPLETED
            drop_session.save()
            return

        send_mob_to_customer(message.source, mc.pmob2mob(drop_session.drop.initial_coin_amount_pmob), True)
        log_and_send_message(drop_session.customer, message.source, "sent initial coin")
        log_and_send_message(drop_session.customer, message.source, "bonus coin payment message request")

        drop_session.state = SESSION_STATE_WAITING_FOR_BONUS_TRANSACTION
        drop_session.save()
        return

    if message.text.lower() == "help":
        log_and_send_message(drop_session.customer, message.source, "initial coins commands verbose")
        return

    log_and_send_message(drop_session.customer, message.source, "initial coins commands")

def handle_drop_session_waiting_for_bonus_transaction(message, drop_session):
    if message.text.lower() == "help":
        log_and_send_message(drop_session.customer, message.source, "waiting for payment commands verbose")
    elif message.text.lower() == "pay":
        log_and_send_message(drop_session.customer, message.source, "paying tutorial")
    elif message.text.lower() == "terms":
        log_and_send_message(drop_session.customer, message.source, "terms of service / purchase")
    else:
        log_and_send_message(drop_session.customer, message.source, "waiting for payment commands")

    log_and_send_message(drop_session.customer, message.source, "payment request message")

def handle_drop_session_complete(message, drop_session):
    log_and_send_message(drop_session.customer, message.source, "You have already participated in this air drop, thanks!")

def handle_drop_sessions(message, drop_session):
    if drop_session.state == SESSION_STATE_COMPLETED:
        handle_drop_session_complete(message, drop_session)
        return

    if drop_session.state == SESSION_STATE_READY_TO_RECEIVE_INITIAL:
        handle_drop_session_ready_to_receive(message, drop_session)
        return

    if drop_session.state == SESSION_STATE_WAITING_FOR_BONUS_TRANSACTION:
        handle_drop_session_waiting_for_bonus_transaction(message, drop_session)
        return

    if drop_session.state == SESSION_STATE_ALLOW_CONTACT_REQUESTED:
        handle_drop_session_allow_contact_requested(message, drop_session)
        return

@signal.chat_handler("coins")
def chat_router_coins(message, match):
    bonus_coins = BonusCoin.objects.all()
    for bonus_coin in bonus_coins:
        number_claimed = DropSession.objects.filter(bonus_coin_claimed=bonus_coin).count()
        signal.send_message(message.source, "{} out of {} {}MOB Bonus Coins claimed ".format(number_claimed, bonus_coin.number_available, mc.pmob2mob(bonus_coin.amount_pmob)))

@signal.chat_handler("")
def chat_router(message, match):
    customer, _ = Customer.objects.get_or_create(phone_number=message.source['number'])
    drop_session = None

    try:
        drop_session = DropSession.objects.get(customer=customer, state__gte=SESSION_STATE_READY_TO_RECEIVE_INITIAL)
    except Exception as e:
        print("NO SESSION FOUND")
        print(e)
        pass

    if drop_session is not None:
        handle_drop_sessions(message, drop_session)
        return

    drops_to_advertise = Drop.objects.filter(advertisment_start_time__lte=timezone.now()).filter(
        start_time__gt=timezone.now())

    if len(drops_to_advertise) > 0:
        drop_to_advertise = drops_to_advertise[0]

        if not customer.phone_number.startswith(drop_to_advertise.number_restriction):
            log_and_send_message(customer, message.source,
                                 "Hi! MOBot here.\n\nSorry, we are not yet available in your country")
            return
        bst_time = drop_to_advertise.start_time.astimezone(pytz.timezone(drop_to_advertise.timezone))
        response_message = "Hi! MOBot here.\n\nWe're currently closed.\n\nCome back on {0} at {1} for {2}".format(
            bst_time.strftime("%A, %b %d"), bst_time.strftime("%-I:%M %p %Z"), drop_to_advertise.item.description)
        log_and_send_message(customer, message.source, response_message)
        return

    active_drops = Drop.objects.filter(start_time__lte=timezone.now()).filter(end_time__gte=timezone.now())
    if len(active_drops) == 0:
        log_and_send_message(customer, message.source, "Hi! MOBot here.\n\nWe're currently closed. Buh-Bye!")
        return

    active_drop = active_drops[0]
    if not customer.phone_number.startswith(active_drop.number_restriction):
        log_and_send_message(customer, message.source, "Hi! MOBot here.\n\nSorry, we are not yet available in your country")
        return

    customer_payments_address = get_payments_address(message.source)
    if customer_payments_address is None:
        log_and_send_message(customer, message.source, "Hi! MOBot here.\n\nI'm a bot from MobileCoin that assists in making purchases using Signal Messenger and MobileCoin\n\nUh oh! In-app payments are not enabled \n\nEnable payments to receive {0}\n\nMore info on enabling payments here: https://support.signal.org/hc/en-us/articles/360057625692-In-app-Payments".format(active_drop.item.description))
        return

    new_drop_session = DropSession(customer=customer, drop=active_drop, state=SESSION_STATE_READY_TO_RECEIVE_INITIAL)
    new_drop_session.save()

    log_and_send_message(customer, message.source, "Are you ready to receive some initial MOB?")

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
