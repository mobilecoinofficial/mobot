import datetime
from logging import Logger
from typing import Optional
from abc import ABC

from django.utils import timezone
from mobot.apps.chat.models import Message, MessageDirection, MobotBot, MobotChatSession
from mobot.apps.merchant_services.models import Customer, CustomerStorePreferences, DropSession, Store, Campaign

from mobot.signald_client.types import Message as SignalMessage
from mobot.signald_client import Signal


class MessageContextBase(ABC):
    customer: Customer
    message: SignalMessage
    campaign: Campaign
    drop_session: DropSession
    mobot: MobotBot
    store: Store
    store_preferences: CustomerStorePreferences
    chat_session: MobotChatSession
    logger: Logger
    signal: Signal

    def log_and_send_message(self, text: str):
        sent_message = Message.objects.create(
            customer=self.customer,
            text=text,
            chat_session=self.chat_session,
            direction=MessageDirection.MESSAGE_DIRECTION_SENT)
        self.signal.send_message(str(self.customer.phone_number), text)


class MessageContextFactory:
    def __init__(self, mobot: MobotBot, root_logger: Logger, signal: Signal):
        self.mobot = mobot
        self.root_logger: Logger = root_logger
        self.signal = signal

    def get_message_context(self, message: SignalMessage = None, customer: Customer = None) -> MessageContextBase:
        class MessageContext(MessageContextBase):
            """Context for current customer"""
            def __init__(self, signal=self.signal, root_logger=self.root_logger, mobot=self.mobot):
                self.signal = signal
                self.customer = self.get_customer_from_message(message) if message else customer
                self.message = message
                self.mobot = mobot
                self.store = mobot.store
                self.chat_session: MobotChatSession = self.get_chat_session_with_customer()
                self.drop_session, drop_session_created = self.get_active_drop_session()
                if drop_session_created:
                    self.chat_session.drop_session = self.drop_session
                    self.chat_session.save()
                self.store_preferences: CustomerStorePreferences = self.get_customer_store_preferences()
                self.logger = root_logger.getChild(f"{message.source}-context")

            def get_customer_from_message(self, message: SignalMessage) -> Customer:
                customer, _ = Customer.objects.get_or_create(phone_number=message.source, name=message.username)
                return customer

            def get_chat_session_with_customer(self) -> MobotChatSession:
                chat_session, _ = MobotChatSession.objects.get_or_create(mobot=self.mobot, customer=self.customer)
                return chat_session

            def get_customer_store_preferences(self) -> CustomerStorePreferences:
                store_preferences, _ = CustomerStorePreferences.objects.get_or_create(customer=self.customer,
                                                                                      store_ref=self.store)
                return store_preferences

            def get_active_drop_session(self) -> DropSession:
                drop_session, created = DropSession.objects.get_or_create(customer=self.customer, campaign=self.mobot.campaign)
                return drop_session, created

            def __enter__(self):
                message_log = Message.objects.create(
                    customer=self.customer,
                    text=self.message.text,
                    chat_session=self.chat_session,
                    created_at=timezone.make_aware(datetime.datetime.utcfromtimestamp(self.message.timestamp)),
                    direction=MessageDirection.MESSAGE_DIRECTION_RECEIVED
                )
                self.logger.info(f"Received message from {self.customer} with {self.message.text}")
                return message_log

            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

        return MessageContext()

