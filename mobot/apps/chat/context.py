import datetime
from logging import Logger
from typing import Optional
from abc import ABC

from django.utils import timezone
from mobot.apps.chat.models import Message, MessageDirection, MobotBot, MobotChatSession
from mobot.apps.merchant_services.models import Customer, CustomerStorePreferences, DropSession, MobotStore, Campaign, Order

from mobot.signald_client.types import Message as SignalMessage
from mobot.lib.signal import Signal
from mobot.lib.signal import SignalCustomerDataClient
from mobilecoin import Client as Fullservice
from mobot.apps.payment_service.service import PaymentService, Payment, Transaction
from django.conf import settings


class MobotContext(ABC):
    customer: Customer
    message: SignalMessage
    campaign: Campaign
    drop_session: DropSession
    order: Order
    mobot: MobotBot
    store: MobotStore
    store_preferences: CustomerStorePreferences
    chat_session: MobotChatSession
    payment_service: PaymentService
    signal_customer_data_client: SignalCustomerDataClient
    logger: Logger
    signal: Signal

    def log_and_send_message(self, text: str):
        Message.objects.create(
            customer=self.customer,
            text=text,
            chat_session=self.chat_session,
            direction=MessageDirection.MESSAGE_DIRECTION_SENT)
        self.signal.send_message(str(self.customer.phone_number), text)

    # FIXME: all amounts should be pmob
    def send_payment_to_user(self, amt_in_pmob: float, customer_payment_address: str, cover_fee=True) -> Payment:
        amt = amt_in_pmob if cover_fee else amt_in_pmob - settings.MINIMUM_FEE_PMOB
        return self.payment_service.submit_payment_to_user(amt_in_mob=amt, customer_payment_address=customer_payment_address)

    def update(self):
        """Update context to get latest versions of DropSession objects etc."""
        pass


class MessageContextManager:
    def __init__(self, mobot: MobotBot, root_logger: Logger, signal: Signal, payment_service: PaymentService):
        self.mobot = mobot
        self.root_logger: Logger = root_logger
        self.signal = signal
        self.payment_service = payment_service

    def get_message_context(self, message: SignalMessage = None, customer: Customer = None) -> MobotContext:
        # Todo: Cache these for the future
        class MessageContext(MobotContext):
            MINIMUM_FEE_PMOB = settings.MINIMUM_FEE_PMOB
            """Context for current customer"""
            def __init__(self, signal=self.signal, root_logger=self.root_logger, mobot=self.mobot, payment_service=self.payment_service):
                self.signal = signal
                # FIXME: Add unittest - message looks like: DEBUG:Mobot-1:Mobot received message: Message(username='+1555555555', source={'number': '+15555555555', 'uuid': 'aaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'}, text='Test', source_device=1, timestamp=1626572253155, timestamp_iso='2021-07-18T01:37:33.155Z', expiration_secs=0, is_receipt=None, attachments=[], quote=None, group_info={}, payment=None)
                self.customer = self.get_customer_from_message(message) if message else customer
                self.payment_service = payment_service
                self.message = message
                self.mobot = mobot
                self.store = mobot.store
                self.campaign = self.mobot.campaign
                self.order = self.get_order()
                self.chat_session: MobotChatSession = self.get_chat_session_with_customer()
                self.drop_session, drop_session_created = self.get_active_drop_session()
                if drop_session_created:
                    self.chat_session.drop_session = self.drop_session
                    self.chat_session.save()
                self.store_preferences: CustomerStorePreferences = self.get_customer_store_preferences()
                self.logger = root_logger.getChild(f"{message.source}-context")

            def get_order(self) -> Optional[Order]:
                try:
                    return Order.objects.get(product__product_group=self.campaign.product_group, customer=self.customer)
                except Order.MultipleObjectsReturned:
                    # FIXME: What should we do here? We should probably make sure you can never add an order if another one is in-flight
                    return None
                except Order.DoesNotExist:
                    return None


            def get_customer_from_message(self, message: SignalMessage) -> Customer:
                customer, _ = Customer.objects.get_or_create(phone_number=message.source['number'], name=message.username)
                return customer

            def get_chat_session_with_customer(self) -> MobotChatSession:
                chat_session, _ = MobotChatSession.objects.get_or_create(mobot=self.mobot, customer=self.customer, slug=self.customer) # FIXME: What should slug/primary key be?
                return chat_session

            def get_customer_store_preferences(self) -> CustomerStorePreferences:
                store_preferences, _ = CustomerStorePreferences.objects.get_or_create(customer=self.customer,
                                                                                      store=self.store)
                return store_preferences

            def get_active_drop_session(self) -> DropSession:
                drop_session, created = DropSession.objects.get_or_create(customer=self.customer, campaign=self.mobot.campaign)
                if drop_session.campaign.is_expired:
                    drop_session.state = DropSession.State.EXPIRED
                    drop_session.save()
                elif drop_session.campaign.not_active_yet:
                    drop_session.state = DropSession.State.NOT_READY
                    drop_session.save()
                return drop_session, created

            def __enter__(self):
                self.logger.debug(f"Entering message context for {message.source}")

                message_log = Message.objects.create(
                    customer=self.customer,
                    text=self.message.text, # FIXME: We need to allow null on the message because of payments and other interim messages with null text
                    chat_session=self.chat_session,
                    created_at=timezone.make_aware(datetime.datetime.utcfromtimestamp(int(self.message.timestamp/100))),
                    direction=MessageDirection.MESSAGE_DIRECTION_RECEIVED
                )
                return message_log

            def __exit__(self, exc_type, exc_val, exc_tb):
                self.drop_session.save()
                self.chat_session.save()
                if self.order:
                    self.order.save()
                pass

        ctx = MessageContext()
        return ctx

