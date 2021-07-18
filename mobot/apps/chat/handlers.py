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


def handle_already_greeted(context: MobotContext):
    context.logger.debug(
        f"User {context.customer.phone_number} already greeted, so handling as if this is an unknown command")
    handle_no_handler_found(context)


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
    context.send_payment_to_user(context.send_payment_to_user(payment.transaction.transaction_amt), cover_fee=False)
    context.log_and_send_message(ChatStrings.UNSOLICITED_PAYMENT)
    return

def handle_order_selected(context: MobotContext):
    selection_id = context.message.text.lower().strip('buy').strip()
    if selection_id.isnumeric():
        product = context.campaign.product_group.products.get(id=int(selection_id))
        _order = Order.objects.order_product(product=product, customer=context.customer)
        context.log_and_send_message(ChatStrings.ITEM_ORDERED_PRICE.format(item=product.name, price=product.price, price_unit=product.price_currency))
    else:
        context.log_and_send_message(ChatStrings.INVALID_PURCHASE_FORMAT)
    # TODO more error handling/incorporate regex assumptions?

def handle_order_payment(context: MobotContext):
    payment: Payment = context.payment_service.get_payment_result(context.message.payment)
    order = context.order
    order.payment = payment
    order.save()
    payment_amount = payment.amount
    overpayment_amount = order.overpayment_amount
    if payment.amount >= order.product.price:
        context.order.state = Order.State.PAYMENT_RECEIVED
    if overpayment_amount:
        overpayment_amount_mob = convert_money(overpayment_amount, MOB)  # Convert to MOB
        context.log_and_send_message(ChatStrings.OVERPAYMENT.format(overpayment_amount=overpayment_amount_mob))
        context.send_payment_to_user(convert_money(overpayment_amount, MOB), cover_fee=False)
