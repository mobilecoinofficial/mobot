from datetime import tzinfo
import os
import pytz

from django.utils import timezone
from django.core.management.base import BaseCommand
from signald_client import Signal
from mobot_client.models import Store, Customer, DropSession, Drop, CustomerStorePreferences, Message

SIGNALD_ADDRESS = os.getenv("SIGNALD_ADDRESS", "127.0.0.1")
SIGNALD_PORT = os.getenv("SIGNALD_PORT", "15432")
STORE_NUMBER = os.environ["STORE_NUMBER"]
signal = Signal(STORE_NUMBER, socket_path=(SIGNALD_ADDRESS, int(SIGNALD_PORT)))

store = Store.objects.get(phone_number=STORE_NUMBER)

SESSION_STATE_COMPLETED = -1
SESSION_STATE_STARTED = 0
SESSION_STATE_ALLOW_CONTACT_REQUESTED = 1

MESSAGE_DIRECTION_RECEIVED = 0
MESSAGE_DIRECTION_SENT = 1

signal.set_profile("MOBot", None, "avatar.png", False)

# catch all chat handler, will perform our own routing from here
@signal.chat_handler("")
def chat_router(message, match):
    customer, _is_new_customer = Customer.objects.get_or_create(phone_number=message.source['number'])
    received_message = Message(customer=customer, store=store, direction=MESSAGE_DIRECTION_RECEIVED, text=message.text)
    received_message.save()

    customer_name = get_signal_profile_name(message.source)
    customer.name = customer_name
    customer.save()

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
