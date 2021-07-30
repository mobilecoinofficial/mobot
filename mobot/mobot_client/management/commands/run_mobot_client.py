# Copyright (c) 2021 MobileCoin. All rights reserved.

from datetime import tzinfo
import os
import time
import pytz
import random

from django.utils import timezone
from django.core.management.base import BaseCommand
from signald_client import Signal
from mobot_client.models import Store, Customer, DropSession, Drop, CustomerStorePreferences, Message, BonusCoin, ChatbotSettings, Order, Sku
import full_service_cli as mc
from decimal import Decimal
import googlemaps

SIGNALD_ADDRESS = os.getenv("SIGNALD_ADDRESS", "127.0.0.1")
SIGNALD_PORT = os.getenv("SIGNALD_PORT", "15432")

store = ChatbotSettings.load().store
signal = Signal(store.phone_number, socket_path=(SIGNALD_ADDRESS, int(SIGNALD_PORT)))

FULLSERVICE_ADDRESS = os.getenv("FULLSERVICE_ADDRESS", "127.0.0.1")
FULLSERVICE_PORT = os.getenv("FULLSERVICE_PORT", "9090")
FULLSERVICE_URL = f"http://{FULLSERVICE_ADDRESS}:{FULLSERVICE_PORT}/wallet"
mcc = mc.Client(url=FULLSERVICE_URL)

GMAPS_CLIENT_KEY = os.environ["GMAPS_CLIENT_KEY"]
gmaps = googlemaps.Client(key=GMAPS_CLIENT_KEY)

all_accounts_response = mcc.get_all_accounts()
ACCOUNT_ID = next(iter(all_accounts_response))
account_obj = all_accounts_response[ACCOUNT_ID]
PUBLIC_ADDRESS = account_obj['main_address']

get_network_status_response = mcc.get_network_status()
MINIMUM_FEE_PMOB = int(get_network_status_response['fee_pmob'])

DROP_TYPE_AIRDROP = 0
DROP_TYPE_ITEM = 1

SESSION_STATE_CANCELLED = -1
SESSION_STATE_READY_TO_RECEIVE_INITIAL = 0
SESSION_STATE_WAITING_FOR_BONUS_TRANSACTION = 1
SESSION_STATE_ALLOW_CONTACT_REQUESTED = 2
SESSION_STATE_COMPLETED = 3

ITEM_SESSION_STATE_REFUNDED = -2
ITEM_SESSION_STATE_CANCELLED = -1
ITEM_SESSION_STATE_WAITING_FOR_PAYMENT = 0
ITEM_SESSION_STATE_WAITING_FOR_SIZE = 1
ITEM_SESSION_STATE_WAITING_FOR_ADDRESS = 2
ITEM_SESSION_STATE_WAITING_FOR_NAME = 3
ITEM_SESSION_STATE_SHIPPING_INFO_CONFIRMATION = 4
ITEM_SESSION_STATE_ALLOW_CONTACT_REQUESTED = 5
ITEM_SESSION_STATE_COMPLETED = 6

ORDER_STATUS_STARTED = 0
ORDER_STATUS_CONFIRMED = 1
ORDER_STATUS_SHIPPED = 2

MESSAGE_DIRECTION_RECEIVED = 0
MESSAGE_DIRECTION_SENT = 1

bot_name = ChatbotSettings.load().name
bot_avatar_filename = ChatbotSettings.load().avatar_filename
b64_public_address = mc.utility.b58_wrapper_to_b64_public_address(PUBLIC_ADDRESS)

resp = signal.set_profile(bot_name, b64_public_address, bot_avatar_filename, True)
print('set profile response', resp)
if resp.get('error'):
    assert False, resp


def send_mob_to_customer(source, amount_mob, cover_transaction_fee):
    if isinstance(source, dict):
        source = source['number']

    customer_payments_address = get_payments_address(source)
    if customer_payments_address is None:
        signal.send_message(source,
                       ("We have a refund for you, but your payments have been deactivated\n\n"
                       "Please contact customer service at {}").format(store.phone_number))
        return

    if not cover_transaction_fee:
        amount_mob = amount_mob - Decimal(mc.pmob2mob(MINIMUM_FEE_PMOB))

    if amount_mob <= 0:
        return

    send_mob_to_address(source, ACCOUNT_ID, amount_mob, customer_payments_address)


def send_mob_to_address(source, account_id, amount_in_mob, customer_payments_address):
    # customer_payments_address is b64 encoded, but full service wants a b58 address
    customer_payments_address = mc.utility.b64_public_address_to_b58_wrapper(customer_payments_address)

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
    receiver_receipt = mc.utility.full_service_receipt_to_b64_receipt(receiver_receipt)
    resp = signal.send_payment_receipt(source, receiver_receipt, "Refund")
    print('Send receipt', receiver_receipt, 'to', source, ':', resp)


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

def handle_item_payment(source, customer, amount_paid_mob, drop_session):
    item_cost_mob = mc.pmob2mob(drop_session.drop.item.price_in_pmob)

    if amount_paid_mob < item_cost_mob:
        if mc.mob2pmob(amount_paid_mob) > MINIMUM_FEE_PMOB:
            log_and_send_message(customer, source, f"Not enough MOB, sending back {amount_paid_mob.normalize()} (minus network fees)")
            send_mob_to_customer(source, amount_paid_mob, False)
        else:
            log_and_send_message(customer, source, "Not enough MOB, unable to refund since it is less than the network fee")
        return
    
    if mc.mob2pmob(amount_paid_mob) > mc.mob2pmob(item_cost_mob) + MINIMUM_FEE_PMOB:
        excess = amount_paid_mob - item_cost_mob
        log_and_send_message(customer, source, f"Sent too much MOB, sending back excess of {excess.normalize()} (minus network fees)")
        send_mob_to_customer(source, excess, False)
    
    available_options = []
    skus = Sku.objects.filter(item=drop_session.drop.item)

    for sku in skus:
        number_ordered = Order.objects.filter(sku=sku).count()
        if number_ordered < sku.quantity:
            available_options.append(sku)
    
    if len(available_options) == 0:
        log_and_send_message(customer, source, f"Uh oh! Looks like we're all out of stock, sorry! Refunding your payment now :)")
        send_mob_to_customer(source, item_cost_mob, True)
        drop_session.state = ITEM_SESSION_STATE_REFUNDED
        drop_session.save()
        return

    message_to_send = "What size would you like? We have the following available options:\n\n"
    for option in available_options:
        message_to_send += f" - {option.identifier}\n"
    
    log_and_send_message(customer, source, message_to_send)
    drop_session.state = ITEM_SESSION_STATE_WAITING_FOR_SIZE
    drop_session.save()

    return

def handle_airdrop_payment(source, customer, amount_paid_mob, drop_session):
    if not minimum_coin_available(drop_session.drop):
        log_and_send_message(customer, source, f"Thank you for sending {amount_paid_mob.normalize()} MOB! Unfortunately, we ran out of MOB to distribute 😭. We're returning your MOB and the network fee.")
        send_mob_to_customer(source, amount_paid_mob, True)
        return

    bonus_coin_objects_for_drop = BonusCoin.objects.filter(drop=drop_session.drop)
    bonus_coins = []

    for bonus_coin in bonus_coin_objects_for_drop:
        number_claimed = DropSession.objects.filter(drop=drop_session.drop, bonus_coin_claimed=bonus_coin).count()
        number_remaining = bonus_coin.number_available - number_claimed
        bonus_coins.extend([bonus_coin] * number_remaining)

    if len(bonus_coins) <= 0:
        log_and_send_message(customer, source, f"Thank you for sending {amount_paid_mob.normalize()} MOB! Unfortunately, we ran out of bonuses 😭. We're returning your MOB and the network fee.")
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

@signal.payment_handler
def handle_payment(source, receipt):
    receipt_status = None
    transaction_status = "TransactionPending"

    if isinstance(source, dict):
        source = source['number']

    print('received receipt', receipt)
    receipt = mc.utility.b64_receipt_to_full_service_receipt(receipt.receipt)

    while transaction_status == "TransactionPending":
        receipt_status = mcc.check_receiver_receipt_status(PUBLIC_ADDRESS, receipt)
        transaction_status = receipt_status["receipt_transaction_status"]
        print('Waiting for', receipt, receipt_status)

    if transaction_status != "TransactionSuccess":
        print('failed', transaction_status)
        return "The transaction failed!"

    amount_paid_mob = mc.pmob2mob(receipt_status["txo"]["value_pmob"])

    customer = None
    drop_session = None

    customer, _ = Customer.objects.get_or_create(phone_number=source)
    try:

        drop_session = DropSession.objects.get(customer=customer, drop__drop_type=DROP_TYPE_AIRDROP, state=SESSION_STATE_WAITING_FOR_BONUS_TRANSACTION)
    except DropSession.DoesNotExist:
        pass
    else:
        handle_airdrop_payment(source, customer, amount_paid_mob, drop_session)
        return

    try:
        drop_session = DropSession.objects.get(customer=customer, drop__drop_type=DROP_TYPE_ITEM, state=ITEM_SESSION_STATE_WAITING_FOR_PAYMENT)
    except DropSession.DoesNotExist:
        log_and_send_message(customer, source, "MOBot here! You sent us an unsolicited payment. We're returning it minus a network fee to cover our costs. We can't promise to always be paying attention and return unsolicited payments, so we suggest only sending us payments when we request them")
        send_mob_to_customer(source, amount_paid_mob, False)
    else:
        handle_item_payment(source, customer, amount_paid_mob, drop_session)

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
        log_and_send_message(drop_session.customer, message.source, f"Our privacy policy is available here: {store.privacy_policy_url}\n\nWould you like to receive alerts for future drops?")
        return

    if message.text.lower() == "help":
        log_and_send_message(drop_session.customer, message.source, "You can type (y)es, (n)o, or (p)rivacy policy\n\nWould you like to receive alerts for future drops?")
        return

    log_and_send_message(drop_session.customer, message.source, "You can type (y)es, (n)o, or (p)rivacy policy\n\nWould you like to receive alerts for future drops?")


def handle_drop_session_ready_to_receive(message, drop_session):
    if message.text.lower() == "n" or message.text.lower() == "no" or message.text.lower() == "cancel":
        drop_session.state = SESSION_STATE_CANCELLED
        drop_session.save()
        log_and_send_message(drop_session.customer, message.source, "session cancelled, message us again when you're ready!")
        return

    if message.text.lower() == "y" or message.text.lower() == "yes":
        if not under_drop_quota(drop_session.drop):
            log_and_send_message(drop_session.customer, message.source, "Too late! We've distributed all of the MOB allocated to this airdrop.\n\nSorry 😭")
            drop_session.state = SESSION_STATE_COMPLETED
            drop_session.save()
            return

        if not minimum_coin_available(drop_session.drop):
            log_and_send_message(drop_session.customer, message.source, "Too late! We've distributed all of the MOB allocated to this airdrop.\n\nSorry 😭")
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
        log_and_send_message(drop_session.customer, message.source, "You can type (y)es, or (n)o\n\nReady?")
        return

    log_and_send_message(drop_session.customer, message.source, "You can type (y)es, or (n)o\n\nReady?")


def handle_drop_session_waiting_for_bonus_transaction(message, drop_session):
    print("----------------WAITING FOR BONUS TRANSACTION------------------")
    if message.text.lower() == "help":
        log_and_send_message(drop_session.customer, message.source, "Commands available are:\n\n?\tQuick list of commands\nhelp\tList of command and what they do\ndescribe\tDescription of drop\npay\tHow to pay")
    elif message.text.lower() == "pay":
        log_and_send_message(drop_session.customer, message.source, "To see your balance and send a payment:\n\n1. Select the attachment icon and select Pay\n\n2. Enter the amount you want to send (e.g. 0.01 MOB)\n\n3. Tap Pay\n\n4. Tap Confirm Payment")
    else:
        log_and_send_message(drop_session.customer, message.source, "Commands are ?, help, describe, and pay\n\n")

    amount_in_mob = mc.pmob2mob(drop_session.drop.initial_coin_amount_pmob)

    value_in_currency = amount_in_mob * Decimal(drop_session.drop.conversion_rate_mob_to_currency)

    log_and_send_message(drop_session.customer, message.source, f"We've sent you {amount_in_mob.normalize()} MOB (~{drop_session.drop.currency_symbol}{value_in_currency:.2f}). Send us 0.01 MOB, and we'll send it back, plus more! You could end up with as much as £50 of MOB")


def handle_active_airdrop_drop_session(message, drop_session):
    if drop_session.state == SESSION_STATE_READY_TO_RECEIVE_INITIAL:
        handle_drop_session_ready_to_receive(message, drop_session)
        return

    if drop_session.state == SESSION_STATE_WAITING_FOR_BONUS_TRANSACTION:
        handle_drop_session_waiting_for_bonus_transaction(message, drop_session)
        return

    if drop_session.state == SESSION_STATE_ALLOW_CONTACT_REQUESTED:
        handle_drop_session_allow_contact_requested(message, drop_session)
        return

def handle_item_drop_session_waiting_for_size(message, drop_session):
    try:
        sku = Sku.objects.get(item=drop_session.drop.item, identifier__iexact=message.text)
    except:
        log_and_send_message(drop_session.customer, message.source, f"No option found for {message.text}")
        return
    
    number_ordered = Order.objects.filter(sku=sku).count()
    if number_ordered >= sku.quantity:
        log_and_send_message(drop_session.customer, message.source, f"Sorry, we're all out of that selection! Refunding your MOB, try again :)")
        price_in_mob = mc.pmob2mob(drop_session.drop.item.price_in_pmob)
        send_mob_to_customer(message.source, price_in_mob, True)
        drop_session.state = ITEM_SESSION_STATE_REFUNDED
        drop_session.save()
        return
    
    new_order = Order(customer=drop_session.customer, drop_session=drop_session, sku=sku)
    new_order.save()

    log_and_send_message(drop_session.customer, message.source, "What address should we send the hoodie to?")
    drop_session.state = ITEM_SESSION_STATE_WAITING_FOR_ADDRESS
    drop_session.save()

def handle_item_drop_session_waiting_for_payment(message, drop_session):
    price_in_mob = mc.pmob2mob(drop_session.drop.item.price_in_pmob)
    log_and_send_message(drop_session.customer, message.source, f"Please send {price_in_mob.normalize()} MOB to reserve your item now!")

def handle_item_drop_session_waiting_for_address(message, drop_session):
    order = None
    try:
        order = Order.objects.get(drop_session=drop_session)
    except:
        log_and_send_message(drop_session.customer, message.source, "We don't seem to have an order for you... something went wrong! Please try again")
        return
    
    address = gmaps.geocode(message.text)

    if len(address) == 0:
        log_and_send_message(drop_session.customer, message.source, "We couldn't seem to find that address. Please try again!")
        return
    
    order.shipping_address = address[0]['formatted_address']
    order.save()

    drop_session.state = ITEM_SESSION_STATE_WAITING_FOR_NAME
    drop_session.save()

    log_and_send_message(drop_session.customer, message.source, "What name should we use to send the order to?")

def handle_item_drop_session_waiting_for_name(message, drop_session):
    order = None
    try:
        order = Order.objects.get(drop_session=drop_session)
    except:
        log_and_send_message(drop_session.customer, message.source, "We don't seem to have an order for you... something went wrong! Please try again")
        return
    
    order.shipping_name = message.text
    order.save()

    drop_session.state = ITEM_SESSION_STATE_SHIPPING_INFO_CONFIRMATION
    drop_session.save()

    log_and_send_message(drop_session.customer, message.source, f"Does this look correct?\n{order.shipping_name}\n{order.shipping_address}")

def handle_item_drop_session_shipping_confirmation(message, drop_session):
    order = None
    try:
        order = Order.objects.get(drop_session=drop_session)
    except:
        log_and_send_message(drop_session.customer, message.source, "We don't seem to have an order for you... something went wrong! Please try again")
        return

    if message.text.lower() == "no" or message.text.lower() == "n":
        drop_session.state = ITEM_SESSION_STATE_WAITING_FOR_ADDRESS
        drop_session.save()
        log_and_send_message(drop_session.customer, message.source, "What address should we ship to?")
        return

    order.status = ORDER_STATUS_CONFIRMED
    order.save()
    
    log_and_send_message(drop_session.customer, message.source, (f"All set. Your order number is {order.id}\n\n"
                                                                f"1x {order.sku.item.name}, to be shipped to you\n\n"
                                                                f"Please provide your order number ({order.id}) when contacting us "
                                                                "if you have any questions or issues"))

    if message.text.lower() == "yes" or message.text.lower() == "y":
        if customer_has_store_preferences(drop_session.customer):
            drop_session.state = ITEM_SESSION_STATE_COMPLETED
            drop_session.save()
            log_and_send_message(drop_session.customer, message.source, "Thanks! MOBot out, buh-bye!")
            return

        drop_session.state = ITEM_SESSION_STATE_ALLOW_CONTACT_REQUESTED
        drop_session.save()
        log_and_send_message(drop_session.customer, message.source, "Can we contact you for future drops?")
    
    log_and_send_message(drop_session.customer, message.source, "Valid commands are y(es) and n(o)")

def handle_item_drop_session_allow_contact_requested(message, drop_session):
    if message.text.lower() == "n" or message.text.lower() == "no":
        customer_store_prefs = CustomerStorePreferences(customer=drop_session.customer, store=store, allows_contact=False)
        customer_store_prefs.save()
        log_and_send_message(drop_session.customer, message.source, "Thanks! MOBot OUT. Buh-bye!")
        drop_session.state = ITEM_SESSION_STATE_COMPLETED
        drop_session.save()
        return

    if message.text.lower() == "y" or message.text.lower() == "yes":
        customer_store_prefs = CustomerStorePreferences(customer=drop_session.customer, store=store, allows_contact=True)
        customer_store_prefs.save()
        log_and_send_message(drop_session.customer, message.source, "Thanks! MOBot OUT. Buh-bye!")
        drop_session.state = ITEM_SESSION_STATE_COMPLETED
        drop_session.save()
        return
    
    log_and_send_message(drop_session.customer, message.source, "You can type (y)es or (n)o\n\nWould you like to receive an alert when we are doing future drops?")

def handle_active_item_drop_session(message, drop_session):
    print(drop_session.state)
    if drop_session.state == ITEM_SESSION_STATE_WAITING_FOR_PAYMENT:
        handle_item_drop_session_waiting_for_payment(message, drop_session)
        return
    
    if drop_session.state == ITEM_SESSION_STATE_WAITING_FOR_SIZE:
        handle_item_drop_session_waiting_for_size(message, drop_session)
        return
    
    if drop_session.state == ITEM_SESSION_STATE_WAITING_FOR_ADDRESS:
        handle_item_drop_session_waiting_for_address(message, drop_session)
        return

    if drop_session.state == ITEM_SESSION_STATE_WAITING_FOR_NAME:
        handle_item_drop_session_waiting_for_name(message, drop_session)
        return

    if drop_session.state == ITEM_SESSION_STATE_SHIPPING_INFO_CONFIRMATION:
        handle_item_drop_session_shipping_confirmation(message, drop_session)
        return
    
    if drop_session.state == ITEM_SESSION_STATE_ALLOW_CONTACT_REQUESTED:
        handle_item_drop_session_allow_contact_requested(message, drop_session)
        return

def customer_has_completed_airdrop(customer, drop):
    try:
        _completed_drop_session = DropSession.objects.get(customer=customer, drop=drop, state=SESSION_STATE_COMPLETED)
        return True
    except:
        return False

def customer_has_completed_item_drop(customer, drop):
    try:
        DropSession.objects.get(customer=customer, drop=drop, state=ITEM_SESSION_STATE_COMPLETED)
        return True
    except:
        return False

def drop_item_has_stock_remaining(drop):
    skus = Sku.objects.fliter(item=drop.item)
    for sku in skus:
        number_ordered = Order.objects.filter(sku=sku).count()
        if number_ordered < sku.quantity:
            return True

    return False

def handle_no_active_item_drop_session(customer, message, drop):
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

    available_options = []
    skus = Sku.objects.filter(item=drop.item)

    for sku in skus:
        number_ordered = Order.objects.filter(sku=sku).count()
        if number_ordered < sku.quantity:
            available_options.append(sku)
    
    if len(available_options) == 0:
        log_and_send_message(customer, message.source, f"Uh oh! Looks like we're all out of stock, sorry!")
        return

    message_to_send = "We have the following available options:\n\n"
    for option in available_options:
        message_to_send += f" - {option.identifier}\n"

    log_and_send_message(customer, message.source, message_to_send)
    price_in_mob = mc.pmob2mob(drop.item.price_in_pmob)
    log_and_send_message(customer, message.source, f"Send {price_in_mob.normalize()} MOB to reserve your item now!")

    new_drop_session, _ = DropSession.objects.get_or_create(customer=customer, drop=drop, state=ITEM_SESSION_STATE_WAITING_FOR_PAYMENT)


def handle_no_active_airdrop_drop_session(customer, message, drop):
    if customer_has_completed_airdrop(customer, drop):
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


@signal.chat_handler("items")
def chat_router_items(message, match):
    active_drop = get_active_drop()
    if active_drop is None:
        return "No active drop to check on items"

    skus = Sku.objects.filter(item=active_drop.item)
    message_to_send = ""
    for sku in skus:
        number_ordered = Order.objects.filter(sku=sku).count()
        message_to_send += f"{sku.identifier} - {number_ordered} / {sku.quantity} ordered\n"
    signal.send_message(message.source, message_to_send)

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
        active_drop_session = DropSession.objects.get(customer=customer, drop__drop_type=DROP_TYPE_AIRDROP, state__gte=SESSION_STATE_READY_TO_RECEIVE_INITIAL, state__lt=SESSION_STATE_COMPLETED)
        
        if active_drop_session.manual_override:
            return

        handle_active_airdrop_drop_session(message, active_drop_session)
        return
    except:
        pass

    try:
        active_drop_session = DropSession.objects.get(customer=customer, drop__drop_type=DROP_TYPE_ITEM, state__gte=ITEM_SESSION_STATE_WAITING_FOR_PAYMENT, state__lt=ITEM_SESSION_STATE_COMPLETED)
        print(f"found active drop session in state {active_drop_session.state}")
        if active_drop_session.manual_override:
            return

        handle_active_item_drop_session(message, active_drop_session)
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

    if active_drop.drop_type == DROP_TYPE_AIRDROP:
        handle_no_active_airdrop_drop_session(customer, message, active_drop)

    if active_drop.drop_type == DROP_TYPE_ITEM:
        handle_no_active_item_drop_session(customer, message, active_drop)

def log_and_send_message(customer, source, text):
    if isinstance(source, dict):
        source = source['number']

    sent_message = Message(customer=customer, store=store, text=text, direction=MESSAGE_DIRECTION_SENT)
    sent_message.save()
    signal.send_message(source, text)


def get_signal_profile_name(source):
    if isinstance(source, dict):
        source = source['number']

    customer_signal_profile = signal.get_profile(source, True)
    try:
        customer_name = customer_signal_profile['data']['name']
        return customer_name
    except:
        return None


def get_payments_address(source):
    if isinstance(source, dict):
        source = source['number']

    customer_signal_profile = signal.get_profile(source, True)
    print(customer_signal_profile)
    return customer_signal_profile.get('mobilecoin_address')


class Command(BaseCommand):
    help = 'Run MOBot Client'

    def handle(self, *args, **kwargs):
        try:
            signal.run_chat(True)
        except KeyboardInterrupt as e:
            print()
            pass
