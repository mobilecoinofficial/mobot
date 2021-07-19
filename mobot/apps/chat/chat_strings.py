from string import Template
from mobot.apps.merchant_services.models import Customer, Campaign, Order

class ChatStrings:
    GREETING = """
            Greetings from MOBot! We're excited to tell you about our latest drop!
            
            Currently, we're offering the following product for sale via MOBot! {campaign_description}
            
            The following commands are available:
            p) View Privacy Policy
            u, unsubscribe) Let us know you don't want to be contacted for future drops
            s, subscribe) Let us know to contact you if you're a match for future drops
            ?) See this message again
            i, inventory) See product inventory
    """


    TRANSACTION_FAILED = "The transaction failed!"
    NOT_READY = "MOBot store is currently closed. The current campaign doesn't begin until {start_time}"
    GOODBYE = "Thanks! MOBot OUT. Buh-bye"
    CAMPAIGN_INACTIVE = "Hi! MOBot here.\n\n We're currently closed. Buh-Bye!"
    NO_INFO_FUTURE_DROPS = "You will no longer receive notifications about future drops."
    NOT_RECEIVING_NOTIFICATIONS = "You are not currently receiving any notifications"
    OFFER = "We'd love to offer you a chance to participate in our latest drop, {drop_description}. Please respond with a (y)es or (n)o."
    OFFER_ACCEPTED = "So glad to hear you're interested! Press i to see our current inventory."
    OFFER_REJECTED = "No worries! If you change your mind, just say hello again and let us know!"
    SUBSCRIBED_ALREADY = "You are already subscribed to receive notifications from this store! Thanks!"
    SUBSCRIBED_FIRST_TIME = "Thanks, we'll let you know about future drops from this store!"
    NOT_VALID_FOR_CAMPAIGN = "Sorry, the current campaign requires a number with a country code of {country_code}"
    DIDNT_UNDERSTAND = "Sorry, I didn't understand that."
    ITEM_ORDERED_PRICE = "You have ordered {item}. Please send me {price} {price_unit}."
    INVALID_PURCHASE_FORMAT = "Please use the format 'buy <item-id>' to place an order. Press i to view the available inventory."

    INVENTORY = """We've got the following items in stock:
        {stock}
        
        To purchase, use the following command:
        
        buy <item-id>
        
        For example, if a product's Item ID is 123, send MOBot:
        
        "buy 123"
    """
    @staticmethod
    def offer_text(customer: Customer, campaign: Campaign) -> str:
        return f"Hey {customer.name} We're happy to offer you the following campaign: {campaign.description}"

    UNSOLICITED_PAYMENT = "MOBot here! You sent us an unsolicited payment. We're returning it minus a network fee to cover our costs. We can't promise to always be paying attention and return unsolicited payments, so we suggest only sending us payments when we request them"
    OVERPAYMENT = "MOBot here! You've overpaid us by {overpayment_amount} for your order. We'll send the overpayment amount back, minus transaction fees."
    ORDER_INVALID = "MOBot here! Something went wrong with your order. We received your payment so we'll return it post haste!"

    PURCHASE_SUCCESSFUL = "Thank you for the payment of {price} for the item {item}. Please enter your address."

    # FIXME: Add address collection flow