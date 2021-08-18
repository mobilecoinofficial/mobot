# Copyright (c) 2021 MobileCoin. All rights reserved.


class ChatStrings:
    # General
    BYE = "Thanks! MOBot OUT. Buh-bye!"

    PRIVACY_POLICY = "Our privacy policy is available here: {url}"
    PRIVACY_POLICY_REPROMPT = """Our privacy policy is available here: {url}

Would you like to receive alerts for future drops?"""

    HELP = """You can type (y)es, (n)o, or (p)rivacy policy
    
Would you like to receive alerts for future drops?"""

    FUTURE_ALERTS = "Would you like to receive alerts for future drops?"
    FUTURE_NOTIFICATIONS = "Can we contact you for future drops?"
    NOTIFICATIONS_HELP = "Valid commands are (y)es and (n)o"
    NOTIFICATIONS_HELP_ALT = """You can type (y)es or (n)o

Would you like to receive an alert when we are doing future drops?"""

    SHIPPING_CONFIRMATION_HELP = """You can type (y)es, (n)o, or (c)ancel

Does this look correct?
{name}
{address}"""

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

More info on enabling payments here: https://support.signal.org/hc/en-us/articles/360057625692-In-app-Payments"""

    UNSOLICITED_PAYMENT = "MOBot here! You sent us an unsolicited payment. We're returning it minus a network fee to cover our costs. We can't promise to always be paying attention and return unsolicited payments, so we suggest only sending us payments when we request them"
    STORE_CLOSED = "Hi! MOBot here.\n\nWe're currently closed.\n\nCome back on {date} at {time} for {desc}"
    STORE_CLOSED_SHORT = "Hi! MOBot here.\n\nWe're currently closed. Buh-Bye!"

    # Session Strings
    SESSION_CANCELLED = """Session cancelled, message us again when you're ready!

MOBot OUT. Buh-bye!"""

    # Payment Strings
    PAYMENTS_DEACTIVATED = """We have a refund for you, but your payments have been deactivated

Please contact customer service at {number}"""

    # Air Drop Strings
    AIRDROP_COMMANDS = """Commands available are:

'describe' - Description of drop
'pay' - How to pay"""

    AIRDROP_RESPONSE = """We've sent you {amount} MOB (~{symbol}{value:.2f}). 

Send us 0.01 MOB, and we'll send it back, plus more! 
You could end up with as much as £50 of MOB"""
    AIRDROP_SUMMARY = (
        "You've received your initial MOB, tried making a payment, "
        "and received a bonus! Well done. You've completed the MOB Coin Drop. "
        "Stay tuned for future drops."
    )
    AIRDROP_INCOMPLETE_SUMMARY = (
        "You've received your MOB but were too late to participate in the bonus round. "
        "You've completed the MOB Coin Drop. "
        "Stay tuned for future drops."
    )
    OVER_QUOTA = (
        "Hi! MOBot here\n\n"
        "It's too late! We've distributed all of the MOB allocated to this airdrop\n\n"
        "Sorry 😭"
    )
    NO_COIN_LEFT = (
       "Hi! MOBot here\n\n"
        "It's too late! We've run out of MOB for this airdrop\n\n"
        "Sorry 😭"
    )
    AIRDROP_DESCRIPTION = (
        "Hi! MOBot here.\n\nWe're giving away free "
        "MOB today so that you can try Signal's new payment feature!!!"
    )
    AIRDROP_INSTRUCTIONS = (
        "Here's how our MOB airdrop works:\n\n"
        "1. We send you some MOB to fund your wallet. It will be approx £3 worth\n"
        "2. Give sending MOB a try by giving us back a tiny bit, say 0.01 MOB\n"
        "3. We'll send you a random BONUS airdrop. You could receive as much as £50 in MOB"
        "\n\nWhether you get £5 or £50, it’s yours to keep and spend however you like"
    )
    READY = "Ready?"
    AIRDROP_OVER = """Too late! We've distributed all of the MOB allocated to this airdrop.

Sorry 😭"""

    AIRDROP_SOLD_OUT_REFUND = """Thank you for sending {amount} MOB! 

Unfortunately, we ran out of MOB to distribute 😭. 
We're returning your MOB and the network fee."""
    BONUS_SOLD_OUT_REFUND = """Thank you for sending {amount} MOB!

Unfortunately, we ran out of bonuses 😭. 
We're returning your MOB and the network fee."""

    AIRDROP_INITIALIZE = """Great! We've just sent you {amount} MOB (~{symbol}{value:.2f})

Send us 0.01 MOB, and we'll send it back, plus more!

You could end up with as much as £50 of MOB"""

    REFUND_SENT = """We've sent you back {amount} MOB! That brings your total prize to {total_prize} MOB"""

    AIRDROP_COMPLETED = """You've completed the MOB Coin Drop! 

To give others a chance, we're only allowing one MOB airdrop per person"""

    PRIZE = """Enjoy your {prize} MOB!"""
    NOTIFICATIONS_ASK = "Would you like to receive alerts for future drops?"

    PAY_HELP = """To see your balance and send a payment:
1. Select the attachment icon and select Pay
2. Enter the amount you want to send (e.g. 0.01 MOB)
3. Tap Pay
4. Tap Confirm Payment
"""

    YES_NO_HELP = """You can type (y)es, or (n)o

Ready?"""

    # Item Drop Strings
    ITEM_DROP_GREETING = """MOBot at your service!

Today's drop is from {store_name}. {store_description}

We have {item_description}"""
    # Item Discount String (used in greeting)
    ITEM_DISCOUNT = """Normally 6 MOB, you can get yours for the discounted price of {price} MOB, shipped. We only ship to the {country}

For pictures, a sizing chart, and more info, type 'info'"""

    NOT_ENOUGH_REFUND = "Not enough MOB, sending back {amount_paid} MOB"
    NOT_ENOUGH = "Not enough MOB, unable to refund since it is less than the network fee"
    EXCESS_PAYMENT = "You overpaid. Sending back {refund} MOB"
    OUT_OF_STOCK = "Uh oh! Looks like we're all out of stock, sorry!"
    # ITEM_SOLD_OUT = (
    #     "Sorry, we're all out of that selection! Refunding your MOB, try again :)"
    # )
    ITEM_SOLD_OUT = """Sorry, we sold out of that size 😔 Please type
- an available size,
- chart for a size chart, or
- cancel for a refund of your payment"""
    ITEM_WHAT_SIZE = "What size would you like?"
    ITEM_WHAT_SIZE_OR_CANCEL = """What size would you like? Type:
- an available size,
- chart for a size chart, or
- cancel for a refund"""

    ITEM_OPTION_CANCEL = """Cancelling your purchase and refunding your payment

MOBot OUT. Buh-bye!"""

    ITEM_OPTION_HELP = """Please type
- an available size,
- chart for a size chart, or
- cancel for a refund of your payment"""
    ITEM_OPTION_NO_CHART = "Sorry. We don't have a picture of the {description}"
    OUT_OF_STOCK_REFUND = "Uh oh! Looks like we're all out of stock, sorry! Refunding your payment now :)"
    ADDRESS_HOODIE_REQUEST = "What address should we send the hoodie to?"
    ADDRESS_REQUEST = "What address should we ship to?"
    ADDRESS_HELP = "Please provide a destination address for shipping the {item}"
    ADDRESS_RESTRICTION = "Sorry, we can only ship to an address in the {country}, please enter a different address!"
    ITEM_HELP = """Commands available are:

'info' - Item info
'privacy' - Privacy policy
'pay' - How to pay"""
# 'terms' - Terms and conditions

    PAYMENT_REQUEST = "Order now by sending {price} MOB using Signal Payments"
    PAY = """1. Select the attachment (+) icon below and then select Pay
2. Enter the amount to send ({amount} MOB)
3. Tap Pay
4. Tap Confirm Payment"""

    TERMS = "Visit {terms} for MOBots terms and conditions"
    WAITING_FOR_SIZE_PREFIX = """What size would you like? Type:
- an available size, or
- chart for a sizing chart.

"""
    ITEM_HELP_SHORT = "Commands are help, info, privacy, and pay\n\n" # removed terms
    RESERVE_ITEM = "Please send {amount} MOB to reserve your item now!"
    MISSING_ORDER = "We don't seem to have an order for you... something went wrong! Please try again"
    ADDRESS_NOT_FOUND = "We couldn't seem to find that address. Please try again!"
    NAME_REQUEST = "For shipping, what name should we use?"
    NAME_HELP = "Please provide the name of the recipient for use on the shipping label"
    VERIFY_SHIPPING = "Does this look correct?\n{name}\n{address}"
    ORDER_CONFIRMATION = """All set. Here is your receipt:
Your order number is {order_id}, order date: {today}

1x {item_name}({sku_name}) for {price} MOB (including item, shipping, and VAT), to be shipped to:

{ship_name}
{ship_address}

Your payment included £{vat:.2f} VAT, collected by MOBot Ltd, VAT ID: {vat_id}

Please provide your order number ({order_id}) when contacting {store_name} at {store_contact} \
if you have any questions or issues"""

    @staticmethod
    def get_options(available_options, capitalize=False):
        option_title = "size"
        if capitalize:
            option_title = option_title.capitalize()
        option_list = list()
        for option in available_options:
            option_list.append(option.identifier)
        if len(option_list) == 1:
            message_to_send = f"{option_title} {option_list[0]} are available"
        else:
            message_to_send = option_title+"s " + ", ".join(option_list[:-1]) + " and " + option_list[-1] + " are availabe"
        return message_to_send

    TIMEOUT = "Your session is about to timeout. Send any message to continue."
    TIMEOUT_CANCELLED = "Your session has expired."
    TIMEOUT_REFUND = "Your session has expired. We will refund the amount you sent."
