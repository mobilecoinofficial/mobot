from string import Template

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
    GOODBYE = "Thanks! MOBot OUT. Buh-bye"
    CAMPAIGN_INACTIVE = "Hi! MOBot here.\n\n We're currently closed. Buh-Bye!"
    NO_INFO_FUTURE_DROPS = "You will no longer receive notifications about future drops."
    NOT_RECEIVING_NOTIFICATIONS = "You are not currently receiving any notifications"
    NOT_VALID_FOR_CAMPAIGN = "Sorry, the current campaign requires a number with a country code of {country_code}"
    DIDNT_UNDERSTAND = "Sorry, I didn't understand that."

    INVENTORY = "We've got {product} in stock in the following sizes"