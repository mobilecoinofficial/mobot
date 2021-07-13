import datetime
from logging import Logger
from typing import Protocol

from django.utils import timezone
from mobot.apps.chat.models import Message, MessageDirection, MobotBot, MobotChatSession
from mobot.apps.merchant_services.models import Customer, CustomerStorePreferences, DropSession, Campaign, Store

from mobot.signald_client.types import Message as SignalMessage


class CustomerContextProtocol(Protocol):
    customer: Customer
    message: SignalMessage
    mobot: MobotBot
    store: Store
    chat_session: MobotChatSession
    logger: Logger


class MessageContextFactory:
    def __init__(self, mobot: MobotBot, logger: Logger):
        self.mobot = mobot
        self.root_logger: Logger = logger

    def get_message_context(self, message: SignalMessage):
        class CustomerContext(CustomerContextProtocol):
            def __init__(self, *args, **kwargs):
                self.customer = self.get_customer_from_number(message)
                self.message = message
                self.mobot = self.mobot
                self.store = self.mobot.store
                self.chat_session: MobotChatSession = self.get_chat_session_with_customer(self.customer)
                self.logger = self.root_logger.getChild(f"{message.source}-context")

            def get_customer_from_message(self, message: SignalMessage) -> Customer:
                customer, _ = Customer.objects.get_or_create(phone_number=message.source)
                return customer

            def get_chat_session_with_customer(self, customer: Customer) -> MobotChatSession:
                chat_session, _ = MobotChatSession.objects.get_or_create(mobot=self.mobot, customer=customer)
                return chat_session

            def get_customer_store_preferences(self, customer: Customer) -> CustomerStorePreferences:
                store_preferences, _ = CustomerStorePreferences.objects.get_or_create(customer=customer,
                                                                                      store=self.store)
                return store_preferences

            def __enter__(self):
                message_log = Message.objects.create(
                    customer=self.customer,
                    text=self.message.text,
                    chat_session=self.chat_session,
                    created_at=timezone.make_aware(datetime.datetime.utcfromtimestamp(self.message.timestamp)),
                    direction=MessageDirection.MESSAGE_DIRECTION_RECEIVED
                )

                self.logger.info(f"Received message from {self.customer} with {self.message.text}")
                pass

            def __exit__(self):
                pass

        return CustomerContext()

