from .context import MessageContextBase
from .chat_strings import ChatStrings
from mobot.apps.merchant_services.models import DropSession, Product, ProductGroup, InventoryItem
from .models import MobotChatSession


def handle_greet_customer(context: MessageContextBase):
    greeting = ChatStrings.GREETING.format(campaign_description=context.campaign.description)
    context.log_and_send_message(greeting)


def unsubscribe_handler(context: MessageContextBase):
    if not context.store_preferences.allows_contact:
        # User already inactive
        context.log_and_send_message(ChatStrings.NOT_RECEIVING_NOTIFICATIONS)
    else:
        context.store_preferences.allows_contact = False
        context.store_preferences.save()
        context.log_and_send_message(ChatStrings.NO_INFO_FUTURE_DROPS)


def inventory_handler(context: MessageContextBase):
    products = context.campaign.product_group.products

    def get_inv_strings():
        for product in products:
            if 0 > product.inventory.count() > 5:
                yield f"{product.name} - In Stock"
            elif product.inventory.count() > 0:
                yield f"{product.name} - Running out - only {product.inventory.count()} left!"
    return "\n   ".join(get_inv_strings())






def privacy_policy_handler(context: MessageContextBase):
    context.log_and_send_message(context.store.privacy_policy_url)


def handle_already_greeted(context: MessageContextBase):
    context.log_and_send_message(ChatStrings.DIDNT_UNDERSTAND)


def handle_validate_customer(context: MessageContextBase):
    if context.customer.phone_number.country_code != context.campaign.number_restriction:
        context.log_and_send_message(ChatStrings.NOT_VALID_FOR_CAMPAIGN.format(context.campaign.number_restriction))
    context.drop_session.state = DropSession.State.FAILED
    context.drop_session.save()


def handle_greet_customer(self, context: MessageContextBase):
    context.log_and_send_message(ChatStrings.GREETING.format(campaign_description=context.campaign.description))
    context.chat_session.state = MobotChatSession.State.INTRODUCTION_GIVEN


def handle_start_conversation(context: MessageContextBase):
    if not context.campaign.is_active():
        context.log_and_send_message(ChatStrings.CAMPAIGN_INACTIVE)
    else:
        if context.customer.phone_number.country_code != context.campaign.number_restriction:
            context.log_and_send_message(ChatStrings.NOT_VALID_FOR_CAMPAIGN.format(context.campaign.number_restriction))