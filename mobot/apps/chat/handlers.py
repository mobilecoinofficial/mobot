from .context import MobotContext
from .chat_strings import ChatStrings
from mobot.apps.merchant_services.models import DropSession, Product, ProductGroup, InventoryItem, Order
from .models import MobotChatSession
from mobot.apps.payment_service.models import Transaction, Payment
from djmoney.contrib.exchange.models import convert_money
import mobilecoin
from django.conf import settings
from .utils import signald_to_fullservice
from mobot.signald_client.types import Message as SignalMessage
from mobot.lib.currency import PMOB, MOB


def handle_greet_customer(context: MobotContext):
    greeting = ChatStrings.GREETING.format(campaign_description=context.campaign.description)
    context.log_and_send_message(greeting)


def unsubscribe_handler(context: MobotContext):
    if not context.store_preferences.allows_contact:
        # User already inactive, send a message letting them know they're already not receiving notifications
        context.log_and_send_message(ChatStrings.NOT_RECEIVING_NOTIFICATIONS)
    else:
        context.store_preferences.allows_contact = False
        context.store_preferences.save()
        context.log_and_send_message(ChatStrings.NO_INFO_FUTURE_DROPS)


def subscribe_handler(context: MobotContext):
    if context.store_preferences.allows_contact:
        context.log_and_send_message(ChatStrings.SUBSCRIBED_ALREADY)
    else:
        # FIXME: Do the subscribe
        context.log_and_send_message(ChatStrings.SUBSCRIBED_FIRST_TIME)


def inventory_handler(context: MobotContext):

    def get_inv_strings():
        for product in context.campaign.product_group.products.iterator():
            if 0 < product.available <= 10: # FIXME: Make this configurable
                yield f"{product.name}(Item ID {product.id}): - In Stock "
            elif product.available > 0:
                yield f"{product.name}(Item ID {product.id}) - Running out - only {product.available} left!"

    inventory_string = "\n   ".join(get_inv_strings())
    message = ChatStrings.INVENTORY.format(stock=inventory_string)
    context.log_and_send_message(message)


def privacy_policy_handler(context: MobotContext):
    context.log_and_send_message(context.store.privacy_policy_url)


def handle_no_handler_found(context: MobotContext):
    context.log_and_send_message(ChatStrings.DIDNT_UNDERSTAND)

# FIXME: This and handle_no_handler_found are getting appended together, so it fires twice
def handle_already_greeted(context: MobotContext):
    context.logger.debug(
        f"User {context.customer.phone_number} already greeted, so handling as if this is an unknown command")
    # handle_no_handler_found(context)


def handle_validate_customer(context: MobotContext):
    if context.customer.phone_number.country_code != context.campaign.number_restriction:
        context.log_and_send_message(
            ChatStrings.NOT_VALID_FOR_CAMPAIGN.format(country_code=context.campaign.number_restriction))
    context.drop_session.state = DropSession.State.FAILED
    context.drop_session.save()


def handle_greet_customer(context: MobotContext):
    context.log_and_send_message(ChatStrings.GREETING.format(campaign_description=context.campaign.description))
    context.chat_session.state = MobotChatSession.State.INTRODUCTION_GIVEN


def handle_drop_expired(context: MobotContext):
    context.log_and_send_message(ChatStrings.CAMPAIGN_INACTIVE)


def handle_drop_not_ready(context: MobotContext):
    context.log_and_send_message(ChatStrings.NOT_READY.format(start_time=context.campaign.start_time))


def handle_start_conversation(context: MobotContext):
    if context.campaign.is_expired:
        context.log_and_send_message(ChatStrings.CAMPAIGN_INACTIVE)
        context.drop_session.state = DropSession.State.EXPIRED
    elif str(context.customer.phone_number.country_code) != context.campaign.number_restriction:
        context.log_and_send_message(
            ChatStrings.NOT_VALID_FOR_CAMPAIGN.format(country_code=context.campaign.number_restriction))
        context.drop_session.state = DropSession.State.FAILED
    elif context.campaign.is_active:
        context.log_and_send_message(ChatStrings.OFFER.format(drop_description=context.campaign.description))
        context.drop_session.state = DropSession.State.OFFERED


def handle_drop_offer_rejected(context: MobotContext):
    context.campaign.quota -= 1
    context.drop_session.state = DropSession.State.CREATED
    context.chat_session.state = MobotChatSession.State.NOT_GREETED
    context.log_and_send_message(ChatStrings.OFFER_REJECTED)


def handle_drop_offer_accepted(context: MobotContext):
    context.drop_session.state = DropSession.State.ACCEPTED
    context.log_and_send_message(ChatStrings.OFFER_ACCEPTED)


def handle_unsolicited_payment(context: MobotContext):
    payment: Payment = context.payment_service.get_payment_result(context.message.payment)
    context.send_payment_to_user(context.send_payment_to_user(float(payment.amount.amount)), cover_fee=False)
    context.log_and_send_message(ChatStrings.UNSOLICITED_PAYMENT)
    return

def handle_order_selected(context: MobotContext):
    selection_id = context.message.text.lower().strip('buy').strip()
    if selection_id.isnumeric():
        product = context.campaign.product_group.products.get(id=int(selection_id))
        _order = Order.objects.order_product(product=product, customer=context.customer)
        # FIXME: convert to MOB
        context.log_and_send_message(ChatStrings.ITEM_ORDERED_PRICE.format(item=product.name, price=product.price.amount, price_unit=product.price_currency))
    else:
        context.log_and_send_message(ChatStrings.INVALID_PURCHASE_FORMAT)
    # TODO more error handling/incorporate regex assumptions?

def handle_order_payment(context: MobotContext):
    payment: Payment = context.payment_service.get_payment_result(context.message.payment)
    order = context.get_order()

    if order is None:
        context.log_and_send_message(ChatStrings.ORDER_INVALID)
        # FIXME: And send back the funds
        return

    order.payment = payment
    order.save()

    print(f"\033[1;36m Got payment amount {payment.amount} but product price is {order.product.price}\033[0m")

    if payment.amount >= order.product.price:
        context.order.state = Order.State.PAYMENT_RECEIVED
        context.order.save()
        # FIXME: payment.amount displays as PMB100,000,000.00
        context.log_and_send_message(ChatStrings.PURCHASE_SUCCESSFUL.format(price=payment.amount, item=context.order.item.product.name))
        return

    # FIXME: Handle below and add tests
    # FIXME: Handle multiple payments for the same order
    if order.overpayment_amount:
        overpayment_amount_pmob = convert_money(order.overpayment_amount, PMOB)  # Convert to PMOB
        context.log_and_send_message(ChatStrings.OVERPAYMENT.format(overpayment_amount=overpayment_amount_pmob))
        context.send_payment_to_user(convert_money(order.overpayment_amount, PMOB), cover_fee=False)

""" For unittests, payment messages look like:

DEBUG:Signal Subscriber:Received message from {'number': '+15555555555', 'uuid': aaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'} with payload None containing payment: {'txo_public_key': '0A20EC3C38D1219046DF8CED52C3262C1D527840EC5DEF50508536F338B3BC64DF14', 'txo_confirmation': '0A20325B43757610C55492B8123D4259AC3792FC9DEC354F5F69FAA21D27F3BA775E', 'tombstone': 160801, 'amount_commitment': '200AC7C93AEA002725B1482E5E7CE9D3E0C786C770523C34E3741FF91E3EC123', 'amount_masked': 7280631925107399455}
DEBUG:Mobot-1:Mobot received message: Message(username='+15555555555', source={'number': '+15555555555', 'uuid': 'aaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'}, text=None, source_device=0, timestamp=1626664443582, timestamp_iso='2021-07-19T03:14:03.582Z', expiration_secs=0, is_receipt=None, attachments=[], quote=None, group_info={}, payment={'txo_public_key': '0A20EC3C38D1219046DF8CED52C3262C1D527840EC5DEF50508536F338B3BC64DF14', 'txo_confirmation': '0A20325B43757610C55492B8123D4259AC3792FC9DEC354F5F69FAA21D27F3BA775E', 'tombstone': 160801, 'amount_commitment': '200AC7C93AEA002725B1482E5E7CE9D3E0C786C770523C34E3741FF91E3EC123', 'amount_masked': 7280631925107399455})
DEBUG:Mobot-1:Attempting to match message: None
DEBUG:Mobot-1.{'number': '+15555555555', 'uuid': 'aaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'}-context:Entering message context for {'number': '+15555555555', 'uuid': 'aaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'}

"""