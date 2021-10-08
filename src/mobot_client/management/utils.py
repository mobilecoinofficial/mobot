from mobot_client.core.context import ChatContext
from mobot_client.models import Customer, ChatbotSettings
from mobot_client.models.messages import Message


def make_context_for_customer(customer: Customer) -> ChatContext:
    store = ChatbotSettings.load().store
    return ChatContext(Message(
        customer=customer,
        store=store,
    ))