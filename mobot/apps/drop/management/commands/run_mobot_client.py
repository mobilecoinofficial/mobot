from datetime import tzinfo
import os
import time
import pytz
import random

from django.utils import timezone
from django.core.management.base import BaseCommand
from mobot.signald_client import Signal
from mobot.apps.merchant_services.models import DropSession, CustomerStorePreferences, Customer, Campaign
import mobilecoin as mc
from decimal import Decimal

SIGNALD_ADDRESS = os.getenv("SIGNALD_ADDRESS", "127.0.0.1")
SIGNALD_PORT = os.getenv("SIGNALD_PORT", "15432")

store = ChatbotSettings.load().store
signal = Signal(store.phone_number, socket_path=(SIGNALD_ADDRESS, int(SIGNALD_PORT)))

FULLSERVICE_ADDRESS = os.getenv("FULLSERVICE_ADDRESS", "127.0.0.1")
FULLSERVICE_PORT = os.getenv("FULLSERVICE_PORT", "9090")
FULLSERVICE_URL = f"http://{FULLSERVICE_ADDRESS}:{FULLSERVICE_PORT}/wallet"
mcc = mc.Client(url=FULLSERVICE_URL)

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



bot_name = ChatbotSettings.load().name
bot_avatar_filename = ChatbotSettings.load().avatar_filename
signal.set_profile(bot_name, PUBLIC_ADDRESS, bot_avatar_filename, False)





def send_mob_to_customer(source, amount_mob, cover_transaction_fee):
    customer_payments_address = get_payments_address(source)
    if customer_payments_address is None:
        signal.send_message(source,
                       ("We have a refund for you, but your payments have been deactivated\n\n"
                       "Please contact customer service at {}").format(store.phone_number))
        return

    if not cover_transaction_fee:
        amount_mob = amount_mob - Decimal(mc.pmob2mob(MINIMUM_FEE_PMOB))

    if amount_mob <= 0:
        signal.send_message(source, "MOBot here! You sent us an unsolicited payment that we can't return. We suggest only sending us payments when we request them and for the amount requested.")
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
    number_initial_drops_finished = DropSession.objects.filter(drop=drop, state__gt=SESSION_STATE_READY_TO_RECEIVE_INITIAL).count()
    return number_initial_drops_finished < drop.initial_coin_limit


def minimum_coin_available(drop):
    account_amount_response = mcc.get_balance_for_account(ACCOUNT_ID)
    unspent_pmob = int(account_amount_response['unspent_pmob'])
    return unspent_pmob >= (drop.initial_coin_amount_pmob + int(MINIMUM_FEE_PMOB))


def get_advertising_drop():
    drops_to_advertise = Drop.objects.filter(advertisment_start_time__lte=timezone.now()).filter(
        start_time__gt=timezone.now())

    if len(drops_to_advertise) > 0:
        return drops_to_advertise[0]
    return None


def get_active_drop():
    active_drops = Drop.objects.filter(start_time__lte=timezone.now()).filter(end_time__gte=timezone.now())
    if len(active_drops) == 0:
        return None
    return active_drops[0]

def get_customer_store_preferences(customer, store_to_check):
    try:
        customer_store_preferences = CustomerStorePreferences.objects.get(customer=customer, store=store_to_check)
        return customer_store_preferences
    except:
        return None

def customer_has_store_preferences(customer):
    try:
        _ = CustomerStorePreferences.objects.get(customer=customer, store=store)
        return True
    except:
        return False


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
        log_and_send_message(customer, source, "MOBot here! You sent us an unsolicited payment. We're returning it minus a network fee to cover our costs. We can't promise to always be paying attention and return unsolicited payments, so we suggest only sending us payments when we request them")
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

    initial_coin_amount_mob = mc.pmob2mob(drop_session.drop.initial_coin_amount_pmob)
    random_index = random.randint(0, len(bonus_coins) - 1)
    amount_in_mob = mc.pmob2mob(bonus_coins[random_index].amount_pmob)
    amount_to_send_mob = amount_in_mob + amount_paid_mob + mc.pmob2mob(MINIMUM_FEE_PMOB)
    send_mob_to_customer(source, amount_to_send_mob, True)
    drop_session.bonus_coin_claimed = bonus_coins[random_index]
    drop_session.save()
    total_prize = Decimal(initial_coin_amount_mob + amount_in_mob)
    log_and_send_message(customer, source, f"We've sent you back {amount_to_send_mob.normalize()} MOB! That brings your total prize to {total_prize.normalize()} MOB")
    log_and_send_message(customer, source, f"Enjoy your {total_prize.normalize()} MOB!")
    log_and_send_message(customer, source, "You've completed the MOB Coin Drop! To give others a chance, we're only allowing one MOB airdrop per person")

    if customer_has_store_preferences(customer):
        log_and_send_message(customer, source, "Thanks! MOBot OUT. Buh-bye")
        drop_session.state = SESSION_STATE_COMPLETED
        drop_session.save()
    else:
        log_and_send_message(customer, source, "Would you like to receive alerts for future drops?")
        drop_session.state = SESSION_STATE_ALLOW_CONTACT_REQUESTED
        drop_session.save()


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

        amount_in_mob = mc.pmob2mob(drop_session.drop.initial_coin_amount_pmob)
        send_mob_to_customer(message.source, amount_in_mob, True)
        log_and_send_message(drop_session.customer, message.source, f"Great! We've just sent you {amount_in_mob.normalize()} MOB (~£3). Send us 0.01 MOB, and we'll send it back, plus more! You could end up with as much as £50 of MOB")
        log_and_send_message(drop_session.customer, message.source, "To see your balance and send a payment:\n\n1. Select the attachment icon and select Pay\n2. Enter the amount you want to send (e.g. 0.01 MOB)\n3. Tap Pay\n4. Tap Confirm Payment")

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


def handle_active_drop_session(message, drop_session):
    if drop_session.state == SESSION_STATE_READY_TO_RECEIVE_INITIAL:
        handle_drop_session_ready_to_receive(message, drop_session)
        return

    if drop_session.state == SESSION_STATE_WAITING_FOR_BONUS_TRANSACTION:
        handle_drop_session_waiting_for_bonus_transaction(message, drop_session)
        return

    if drop_session.state == SESSION_STATE_ALLOW_CONTACT_REQUESTED:
        handle_drop_session_allow_contact_requested(message, drop_session)
        return


def customer_has_completed_drop(customer, drop):
    try:
        _completed_drop_session = DropSession.objects.get(customer=customer, drop=drop, state=SESSION_STATE_COMPLETED)
        return True
    except:
        return False


def handle_no_active_drop_session(customer, message, drop):
    if customer_has_completed_drop(customer, drop):
        log_and_send_message(customer, message.source,
                             ("You've received your initial MOB, tried making a payment, "
                              "and received a bonus! Well done. You've completed the MOB Coin Drop. "
                              "Stay tuned for future drops."))
        return

    if not customer.phone_number.startswith(drop.number_restriction):
        log_and_send_message(customer, message.source,
                             "Hi! MOBot here.\n\nSorry, we are not yet available in your country")
        return

    customer_payments_address = get_payments_address(message.source)
    if customer_payments_address is None:
        log_and_send_message(customer, message.source,
                             ("Hi! MOBot here.\n\nI'm a bot from MobileCoin that assists "
                              "in making purchases using Signal Messenger and MobileCoin\n\n"
                              "Uh oh! In-app payments are not enabled \n\n"
                              f"Enable payments to receive {drop.item.description}\n\n"
                              "More info on enabling payments here: "
                              "https://support.signal.org/hc/en-us/articles/360057625692-In-app-Payments"))
        return

    if not under_drop_quota(drop):
        log_and_send_message(customer, message.source, "over quota for drop!")
        return

    if not minimum_coin_available(drop):
        log_and_send_message(customer, message.source, "no coin left!")
        return

    new_drop_session = DropSession(customer=customer, drop=drop, state=SESSION_STATE_READY_TO_RECEIVE_INITIAL)
    new_drop_session.save()

    log_and_send_message(customer, message.source,
                         ("Hi! MOBot here.\n\nWe're giving away free "
                          "MOB today so that you can try Signal's new payment feature!!!"))
    log_and_send_message(customer, message.source,
                         ("Here's how our MOB airdrop works:\n\n"
                          "1. We send you some MOB to fund your wallet. It will be approx £3 worth\n"
                          "2. Give sending MOB a try by giving us back a tiny bit, say 0.01 MOB\n"
                          "3. We'll send you a random BONUS airdrop. You could receive as much as £50 in MOB"
                          "\n\nWhether you get £5 or £50, it’s yours to keep and spend however you like"))
    log_and_send_message(customer, message.source, "Ready?")


@signal.chat_handler("coins")
def chat_router_coins(message, match):
    bonus_coins = BonusCoin.objects.all()
    for bonus_coin in bonus_coins:
        number_claimed = DropSession.objects.filter(bonus_coin_claimed=bonus_coin).count()
        signal.send_message(message.source, f"{number_claimed} out of {bonus_coin.number_available} {mc.pmob2mob(bonus_coin.amount_pmob).normalize()}MOB Bonus Coins claimed ")


@signal.chat_handler("privacy")
def privacy_policy_handler(message, _match):
    customer, _is_new = Customer.objects.get_or_create(phone_number=message.source['number'])
    log_and_send_message(customer, message.source, store.privacy_policy_url)
    return


@signal.chat_handler("unsubscribe")
def unsubscribe_handler(message, _match):
    customer, _is_new = Customer.objects.get_or_create(phone_number=message.source['number'])
    store_preferences, _is_new = CustomerStorePreferences.objects.get_or_create(customer=customer, store=store)

    if not store_preferences.allows_contact:
        log_and_send_message(customer, message.source, "You are not currently receiving any notifications")
        return

    store_preferences.allows_contact = False
    store_preferences.save()

    log_and_send_message(customer, message.source, "You will no longer receive notifications about future drops.")


@signal.chat_handler("subscribe")
def subscribe_handler(message, _match):
    customer, _is_new = Customer.objects.get_or_create(phone_number=message.source['number'])
    store_preferences, _is_new = CustomerStorePreferences.objects.get_or_create(customer=customer, store=store)

    if store_preferences.allows_contact:
        log_and_send_message(customer, message.source, "You are already subscribed.")
        return

    store_preferences.allows_contact = True
    store_preferences.save()

    log_and_send_message(customer, message.source, "We will let you know about future drops!")


@signal.chat_handler("")
def chat_router(message, match):
    customer, _ = Customer.objects.get_or_create(phone_number=message.source['number'])
    try:
        active_drop_session = DropSession.objects.get(customer=customer, state__gte=SESSION_STATE_READY_TO_RECEIVE_INITIAL, state__lt=SESSION_STATE_COMPLETED)
        handle_active_drop_session(message, active_drop_session)
        return
    except:
        pass

    drop_to_advertise = get_advertising_drop()
    if drop_to_advertise is not None:
        if not customer.phone_number.startswith(drop_to_advertise.number_restriction):
            log_and_send_message(customer, message.source,
                                 "Hi! MOBot here.\n\nSorry, we are not yet available in your country")
            return
        bst_time = drop_to_advertise.start_time.astimezone(pytz.timezone(drop_to_advertise.timezone))
        response_message = "Hi! MOBot here.\n\nWe're currently closed.\n\nCome back on {0} at {1} for {2}".format(
            bst_time.strftime("%A, %b %d"), bst_time.strftime("%-I:%M %p %Z"), drop_to_advertise.item.description)
        log_and_send_message(customer, message.source, response_message)
        return

    active_drop = get_active_drop()
    if active_drop is None:
        log_and_send_message(customer, message.source, "Hi! MOBot here.\n\nWe're currently closed. Buh-Bye!")
        return

    handle_no_active_drop_session(customer, message, active_drop)


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