# Copyright (c) 2021 MobileCoin. All rights reserved.


class ChatStrings:

    # General
    BYE = "Thanks! MOBot OUT. Buh-bye!"
    FUTURE_NOTIFICATIONS = "Can we contact you for future drops?"
    NOTIFICATIONS_HELP = "Valid commands are y(es) and n(o)"
    NOTIFICATIONS_HELP_ALT = """You can type (y)es or (n)o

    Would you like to receive an alert when we are doing future drops?
    """
    NOTIFICATIONS_OFF = "You are not currently receiving any notifications"
    DISABLE_NOTIFICATIONS = (
        "You will no longer receive notifications about future drops."
    )
    ALREADY_SUBSCRIBED = "You are already subscribed."
    SUBSCRIBE_NOTIFICATIONS = "We will let you know about future drops!"
    COUNTRY_RESTRICTED = (
        "Hi! MOBot here.\n\nSorry, we are not yet available in your country"
    )
    PAYMENTS_ENABLED_HELP = """Hi! MOBot here.

    I'm a bot from MobileCoin that assists in making purchases using Signal Messenger and MobileCoin.

    Uh oh! In-app payments are not enabled

    Enable payments to receive {item_desc}

    More info on enabling payments here: https://support.signal.org/hc/en-us/articles/360057625692-In-app-Payments
    """
    UNSOLICITED_PAYMENT = "MOBot here! You sent us an unsolicited payment. We're returning it minus a network fee to cover our costs. We can't promise to always be paying attention and return unsolicited payments, so we suggest only sending us payments when we request them"
    STORE_CLOSED = "Hi! MOBot here.\n\nWe're currently closed.\n\nCome back on {date} at {time} for {desc}"
    STORE_CLOSED_SHORT = "Hi! MOBot here.\n\nWe're currently closed. Buh-Bye!"

    # Item Drop Strings
    OUT_OF_STOCK = "Uh oh! Looks like we're all out of stock, sorry!"
    ITEM_SOLD_OUT = (
        "Sorry, we're all out of that selection! Refunding your MOB, try again :)"
    )
    ADDRESS_HOODIE_REQUEST = "What address should we send the hoodie to?"
    ADDRESS_REQUEST = "What address should we ship to?"
    ITEM_HELP = """Commands available are:

    'info' - Item info
    'pay' - How to pay
    'terms' - Terms and conditions
    """
    PAYMENT_REQUEST = "Send {price} MOB to reserve your item now!"
    PAY = """1. Select the attachment (+) icon below and then select Pay

    2. Enter the amount to send ({amount} MOB)
    3. Tap Pay
    4. Tap Confirm Payment
    """
    TERMS = "Visit (terms url) for MOBots terms and conditions"
    ITEM_HELP_SHORT = "Commands are help, info, pay, and terms\n\n"
    RESERVE_ITEM = "Please send {amount} MOB to reserve your item now!"
    MISSING_ORDER = "We don't seem to have an order for you... something went wrong! Please try again"
    ADDRESS_NOT_FOUND = "We couldn't seem to find that address. Please try again!"
    NAME_REQUEST = "What name should we use to send the order to?"
    VERIFY_SHIPPING = "Does this look correct?\n{name}\n{address}"
    ORDER_CONFIRMATION = """All set. Your order number is {order_id}

    1x {sku_name}, to be shipped to you

    Please provide your order number ({order_id}) when contacting us
    if you have any questions or issues
    """

    @staticmethod
    def get_options(available_options):
        message_to_send = "We have the following available options:\n\n"
        for option in available_options:
            message_to_send += f" - {option.identifier}\n"

        return message_to_send
