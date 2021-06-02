import os
import time
import pytz

from django.utils import timezone
from django.core.management.base import BaseCommand

from mobot.signald_client import Signal
from mobot.apps.mobot_client.models import Store, Customer, DropSession, Drop, CustomerStorePreferences, Message
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

PUBLIC_ADDRESS = os.environ["PUBLIC_ADDRESS"]
ACCOUNT_ID = os.environ["ACCOUNT_ID"]

store = Store.objects.get(phone_number=STORE_NUMBER)

SESSION_STATE_COMPLETED = -1
SESSION_STATE_STARTED = 0
SESSION_STATE_ALLOW_CONTACT_REQUESTED = 1

MESSAGE_DIRECTION_RECEIVED = 0
MESSAGE_DIRECTION_SENT = 1

signal.set_profile("MOBot - Local Brian", PUBLIC_ADDRESS, None, False)

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
                       "Please contact customer service at {}").format(STORE_NUMBER))
        return
    
    if not cover_transaction_fee:
        amount_mob = amount_mob - Decimal(0.01)

    if amount_mob <= 0:
        signal.send_message(source, "Sorry. Can't issue a refund because the refund amount is less than the transaction fee 🙁")
        return

    send_mob_to_user(source, ACCOUNT_ID, amount_mob, customer_payments_address)

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

@signal.chat_handler("balance")
def account_balance(message, match):
    account_balance_response = mcc.get_balance_for_account(ACCOUNT_ID)
    unspent_pmob = account_balance_response['unspent_pmob']
    unspent_mob = mc.pmob2mob(unspent_pmob)
    return f'You have {unspent_mob} unspent MOB'

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
    refund_customer(source, amount_paid_mob, False)

# catch all chat handler, will perform our own routing from here
@signal.chat_handler("")
def chat_router(message, match):
    customer, _is_new_customer = Customer.objects.get_or_create(phone_number=message.source['number'])
    received_message = Message(customer=customer, store=store, direction=MESSAGE_DIRECTION_RECEIVED, text=message.text)
    received_message.save()

    try:
        drop_session = DropSession.objects.get(customer=customer, state__gte=SESSION_STATE_STARTED)

        if drop_session.state == SESSION_STATE_ALLOW_CONTACT_REQUESTED:
            if message.text.lower() == "y" or message.text.lower() == "yes":
                customer_prefs = CustomerStorePreferences(customer=customer, store=store, allows_contact=True)
                customer_prefs.save()
                drop_session.state = SESSION_STATE_COMPLETED
                drop_session.save()
                log_and_send_message(customer, message.source, "Thanks! MOBot OUT. Buh-bye")
                return
            
            if message.text.lower() == "n" or message.text.lower() == "no":
                customer_prefs = CustomerStorePreferences(customer=customer, store=store, allows_contact=False)
                customer_prefs.save()
                drop_session.state = SESSION_STATE_COMPLETED
                drop_session.save()
                log_and_send_message(customer, message.source, "Thanks! MOBot OUT. Buh-bye")
                return

            if message.text.lower().startswith("p"):
                log_and_send_message(customer, message.source, "Our privacy policy is available here: {0}\n\nWould you like to receive alerts for future drops?".format(store.privacy_policy_url))
                return
            
            if message.text.lower() == "cancel":
                drop_session.state = SESSION_STATE_COMPLETED
                drop_session.save()
                log_and_send_message(customer, message.source, "Your session has been cancelled")
                return
            
            log_and_send_message(customer, message.source, "You can type (y)es, (n)o, or (p)rivacy policy\n\nWould you like to receive alerts for future drops?")
            return
    except:
        pass

    # if customer.received_sticker_pack:
    #     log_and_send_message(customer, message.source, "Looks like you've already received a sticker pack! MOBot OUT. Buh-bye")
    #     return

    drops_to_advertise = Drop.objects.filter(advertisment_start_time__lte=timezone.now()).filter(start_time__gt=timezone.now())

    if len(drops_to_advertise) > 0:
        drop_to_advertise = drops_to_advertise[0]

        if not customer.phone_number.startswith(drop_to_advertise.number_restriction):
            log_and_send_message(customer, message.source, "Hi! MOBot here.\n\nSorry, we are not yet available in your country")
            return
        bst_time = drop_to_advertise.start_time.astimezone(pytz.timezone(drop_to_advertise.timezone))
        response_message = "Hi! MOBot here.\n\nWe're currently closed.\n\nCome back on {0} at {1} for {2}".format(bst_time.strftime("%A, %b %d"), bst_time.strftime("%-I:%M %p %Z"), drop_to_advertise.item.description)
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

    log_and_send_message(customer, message.source, "Looks like you have everything set up! Here's your digital sticker pack")
    log_and_send_message(customer, message.source, "https://signal.art/addstickers/#pack_id=83d4f5b9a0026fa6ffe1b1c0f11a2018&pack_key=6b03ace1a84b31589ce231a74ad914733217cea9ba47a411a9abe531aab8e55a")

    customer.received_sticker_pack = True
    customer.save()

    try:
        _ = CustomerStorePreferences.objects.get(customer=customer, store=store)
        new_drop_session = DropSession(customer=customer, drop=active_drop, state=SESSION_STATE_COMPLETED)
        new_drop_session.save()
        log_and_send_message(customer, message.source, "Thanks! MOBot OUT. Buh-bye")
        return
    except:
        new_drop_session = DropSession(customer=customer, drop=active_drop, state=SESSION_STATE_ALLOW_CONTACT_REQUESTED)
        new_drop_session.save()
        log_and_send_message(customer, message.source, "Would you like to receive alerts for future drops?")
        return

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
