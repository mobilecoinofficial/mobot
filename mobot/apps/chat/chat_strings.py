from string import Template

GREETING = """
        Thank you for greeting Mobot. The message you sent was {message_text}
        I'm a {name} serving drops for {store} and I'm happy to meet you!
        
        The following commands are available:
        p) View Privacy Policy
        u, unsubscribe) Let us know you don't want to be contacted for future drops
        s, subscribe) Let us know to contact you if you're a match for future drops
        ?) See this message again
"""

TRANSACTION_FAILED = "The transaction failed!"
GOODBYE = "Thanks! MOBot OUT. Buh-bye"
NO_INFO_FUTURE_DROPS = "You will no longer receive notifications about future drops."
NOT_RECEIVING_NOTIFICATIONS = "You are not currently receiving any notifications"
