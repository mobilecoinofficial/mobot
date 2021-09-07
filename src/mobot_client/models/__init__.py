#  Copyright (c) 2021 MobileCoin. All rights reserved.

from __future__ import annotations
import random
import logging

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from decimal import Decimal
from typing import Optional, Union, Callable

import pytz
from django.db import models
from django.db.models import F, Q, Sum
from django.utils import timezone
from django.utils.functional import cached_property
from django.db import transaction
from django.conf import settings
from phonenumber_field.modelfields import PhoneNumberField
from signald.types import Message as SignalMessage, Payment as SignalPayment

from mobot_client.models.states import SessionState
from mobot_client.models.states import SessionState
import mobilecoin as mc



class SessionException(Exception):
    pass


class OutOfStockException(SessionException):
    pass


class Store(models.Model):
    name = models.CharField(max_length=255)
    phone_number = PhoneNumberField(db_index=True)
    description = models.TextField()
    privacy_policy_url = models.URLField()

    def __str__(self):
        return f"{self.name} [{self.phone_number.as_e164}]"


class Item(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="items")
    name = models.CharField(max_length=255)
    price_in_pmob = models.PositiveIntegerField(default=None, blank=True, null=True)
    description = models.TextField(default=None, blank=True, null=True)
    short_description = models.TextField(default=None, blank=True, null=True)
    image_link = models.URLField(default=None, blank=True, null=True)

    @property
    def price_in_mob(self) -> Decimal:
        return mc.pmob2mob(self.price_in_pmob)

    def __str__(self):
        return f"{self.name}"


class AvailableSkuManager(models.Manager):
    def get_queryset(self) -> models.QuerySet:
        return super().get_queryset() \
            .annotate(number_ordered=models.Count('orders'),
                      available=F('quantity') - models.Count('orders')) \
            .filter(available__gt=0)


class Sku(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="skus")
    identifier = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=0)
    sort_order = models.PositiveIntegerField(default=0)

    available = AvailableSkuManager()
    objects = models.Manager()

    class Meta:
        unique_together = ('item', 'identifier')
        base_manager_name = 'available'
        ordering = ['sort_order']

    def __str__(self) -> str:
        return f"{self.item.name} - {self.identifier}"

    def number_ordered(self) -> int:
        return self.orders.count()

    def number_available(self) -> int:
        return self.quantity - self.number_ordered()

    def in_stock(self) -> bool:
        return self.number_available() > 0

    @transaction.atomic()
    def order(self, drop_session: DropSession) -> Order:
        # Need to check whether this is in-stock again, just in case!
        if self.in_stock():
            return Order.objects.create(customer=drop_session.customer,
                                        drop_session=drop_session,
                                        sku=self,
                                        conversion_rate_mob_to_currency=drop_session.drop.conversion_rate_mob_to_currency)
        else:
            raise OutOfStockException(f"Unable to complete order; Item {self.identifier} out of stock!")


class DropType(models.IntegerChoices):
    AIRDROP = 0, 'airdrop'
    ITEM = 1, 'item'

    def __str__(self):
        return self.label


class DropQuerySet(models.QuerySet):
    def advertising_drops(self) -> models.QuerySet:
        return self.filter(
            advertisment_start_time__lte=timezone.now(),
            end_time__lte=timezone.now()
        )

    def active_drops(self) -> models.QuerySet:
        return self.filter(
            start_time__lte=timezone.now(),
            end_time__gte=timezone.now()
        )


class DropManager(models.Manager.from_queryset(DropQuerySet)):
    logger = logging.getLogger("DropLogger")

    def advertising_drops(self) -> DropQuerySet:
        return self.get_queryset().advertising_drops()

    def get_advertising_drop(self):
        return self.advertising_drops().first()

    def active_drops(self) -> DropQuerySet:
        return self.get_queryset().active_drops()

    def get_active_drop(self) -> Optional[Drop]:
        return self.active_drops().first()


class Drop(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='drops')
    drop_type = models.IntegerField(choices=DropType.choices, default=DropType.AIRDROP, db_index=True)
    pre_drop_description = models.TextField()
    advertisment_start_time = models.DateTimeField(db_index=True)
    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField(db_index=True)
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='drops', db_index=True, null=True, blank=True)
    number_restriction = models.CharField(default="+44", max_length=4)
    timezone = models.CharField(default="UTC", max_length=255)
    initial_coin_amount_pmob = models.PositiveIntegerField(default=0)
    conversion_rate_mob_to_currency = models.FloatField(default=1.0)
    currency_symbol = models.CharField(default="£", max_length=1)
    country_code_restriction = models.CharField(default="GB", max_length=3)
    country_long_name_restriction = models.CharField(default="United Kingdom", max_length=255)
    max_refund_transaction_fees_covered = models.PositiveIntegerField(default=0)
    name = models.CharField(default="A drop", db_index=True, max_length=255)

    objects = DropManager()

    def clean(self):
        assert self.start_time < self.end_time
        if self.drop_type == DropType.ITEM:
            assert self.item is not None

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def value_in_currency(self, amount: Decimal) -> Decimal:
        return amount * Decimal(self.conversion_rate_mob_to_currency)

    @cached_property
    def initial_coin_limit(self) -> int:
        if bonus_coins := self.bonus_coins.aggregate(Sum('number_available_at_start'))['number_available_at_start__sum']:
            return bonus_coins
        else:
            return 0

    def num_initial_sent(self) -> int:
        return DropSession.objects.initial_coin_sent_sessions().filter(drop=self).count()

    def num_bonus_sent(self) -> int:
        return BonusCoin.objects.with_available().filter(drop=self).aggregate(Sum('num_claimed_sessions'))['num_claimed_sessions__sum']

    def bonus_pmob_disbursed(self) -> int:
        if self.bonus_coins.count():
            return BonusCoin.objects.with_available().filter(drop=self).aggregate(Sum('pmob_claimed'))['pmob_claimed__sum']
        else:
            return 0

    def initial_pmob_disbursed(self) -> int:
        return self.num_initial_sent() * self.initial_coin_amount_pmob

    def initial_coins_available(self) -> Union[int, str]:
        if self.drop_type == DropType.AIRDROP:
            return self.initial_coin_limit - self.num_initial_sent()
        else:
            return "N/A"

    def total_pmob_spent(self) -> int:
        return self.initial_pmob_disbursed() + self.bonus_pmob_disbursed()

    def under_quota(self) -> bool:
        if self.drop_type == DropType.AIRDROP:
            DropManager.logger.debug("Checking if there are coins available to give out...")
            active_drop_sessions_count = DropSession.objects.sold_sessions().filter(drop=self).count()
            DropManager.logger.debug(
                f"There are {active_drop_sessions_count} sessions on this airdrop with an initial limit of {self.initial_coin_limit}"
            )
            return active_drop_sessions_count < self.initial_coin_limit and self.initial_coins_available() > 0
        else:
            return len(self.item.skus) > 0

    def is_active(self) -> bool:
        if self.start_time and self.end_time:
            return self.start_time < timezone.now() < self.end_time
        else:
            return False

    def __str__(self):
        return f"{self.store.name}-{self.name}"


class BonusCoinQuerySet(models.QuerySet):
    def with_available(self):
        return self.annotate(
            num_claimed_sessions=models.Count('drop_sessions', filter=Q(drop_sessions__state=SessionState.ALLOW_CONTACT_REQUESTED))) \
            .filter(num_claimed_sessions__lt=F('number_available_at_start')) \
            .annotate(remaining=F('number_available_at_start') - F('num_claimed_sessions'),
                      pmob_claimed=F('num_claimed_sessions') * F('amount_pmob'))

    def available_coins(self):
        return self.with_available().filter(remaining__gt=0)


class BonusCoinManager(models.Manager.from_queryset(BonusCoinQuerySet)):

    @transaction.atomic
    def claim_random_coin(self, drop_session):
        coins_available = self.available_coins().select_for_update().filter(remaining__gt=0)
        coins_dist = [coin.remaining for coin in coins_available]
        if coins_available.count() > 0:
            coin = random.choices(list(coins_available), weights=coins_dist)[0]
            drop_session.bonus_coin_claimed = coin
            drop_session.state = SessionState.ALLOW_CONTACT_REQUESTED
            drop_session.save()
            return coin
        else:
            drop_session.state = SessionState.OUT_OF_STOCK
            drop_session.save()
            raise OutOfStockException("No more coins available to give out!")


class BonusCoin(models.Model):
    drop = models.ForeignKey(Drop, on_delete=models.CASCADE, related_name='bonus_coins', db_index=True)
    amount_pmob = models.PositiveIntegerField(default=0)
    number_available_at_start = models.PositiveIntegerField(default=0)

    objects = BonusCoinManager()

    def __str__(self):
        return f"BonusCoin ({self.amount_pmob} PMOB)"

    def number_remaining(self) -> int:
        sold = DropSession.objects.sold_sessions().filter(drop=self.drop, bonus_coin_claimed=self).count()
        return self.number_available_at_start - sold

    def number_claimed(self) -> int:
        return self.number_available_at_start - self.number_remaining()


class Customer(models.Model):
    phone_number = PhoneNumberField(db_index=True, unique=True)
    received_sticker_pack = models.BooleanField(default=False)

    def matches_country_code_restriction(self, drop: Drop) -> bool:
        return f"+{self.phone_number.country_code}" == drop.number_restriction

    def active_drop_sessions(self):
        return DropSession.objects.active_drop_sessions().filter(customer=self)

    def has_active_drop_session(self) -> bool:
        return self.drop_sessions.count() > 0

    def state(self) -> Optional[SessionState]:
        if active_session := self.active_drop_sessions().first():
            return active_session.get_state_display()
        else:
            return None

    def sessions_awaiting_payment(self):
        return DropSession.objects.awaiting_payment_sessions()

    def has_session_awaiting_payment(self):
        return self.sessions_awaiting_payment().count() > 0

    has_session_awaiting_payment.short_description = "Awaiting Payment"

    def fulfilled_drop_sessions(self):
        return DropSession.objects.sold_sessions().filter(customer=self)

    def has_fulfilled_drop_session(self):
        return self.fulfilled_drop_sessions().count() > 0

    has_fulfilled_drop_session.short_description = "Fulfilled"

    def completed_drop_sessions(self):
        return DropSession.objects.completed_sessions().filter(customer=self)

    def has_completed_session(self):
        return self.completed_drop_sessions().count() > 0

    has_completed_session.short_description = "Completed"

    def errored_sessions(self):
        return DropSession.objects.errored_sessions().filter(customer=self)

    def successful_sessions(self):
        '''Return customer sessions with a sale completed'''
        return DropSession.objects.sold_sessions().filter(customer=self)

    def has_completed_drop(self, drop: Drop) -> bool:
        completed_drop = self.fulfilled_drop_sessions().filter(drop=drop).first()
        return completed_drop is not None

    def has_completed_drop_with_error(self, drop: Drop) -> bool:
        return self.errored_sessions().filter(drop=drop).count() > 0

    def store_preferences(self, store: Store):
        return self.customer_store_preferences.filter(store=store).first()

    def has_store_preferences(self, store: Store) -> bool:
        return self.store_preferences(store) is not None

    def __str__(self):
        return f"{self.phone_number.as_e164}"


class CustomerStorePreferences(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="customer_store_preferences",
                                 db_index=True)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="customer_store_preferences", db_index=True)
    allows_contact = models.BooleanField()

    def __str__(self):
        return f"{self.customer}:{self.store}"


class CustomerDropRefunds(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="drop_refunds", db_index=True)
    drop = models.ForeignKey(Drop, on_delete=models.CASCADE, related_name="drop_refunds", db_index=True)
    number_of_times_refunded = models.PositiveIntegerField(default=0)


class DropSessionQuerySet(models.QuerySet):
    def active_drop_sessions(self):
        return self.filter(
            state__lt=SessionState.COMPLETED,
            state__gte=SessionState.READY,
            drop__start_time__lte=timezone.now(),
            drop__end_time__gte=timezone.now())

    def initial_coin_sent_sessions(self):
        return self.filter(
            state__gt=SessionState.READY,
            drop__start_time__lte=timezone.now(),
            drop__end_time__gte=timezone.now())

    def awaiting_payment_sessions(self):
        return self.filter(
            state=SessionState.WAITING_FOR_PAYMENT,
            drop__start_time__lte=timezone.now(),
            drop__end_time__gte=timezone.now(),
        )

    def errored_sessions(self):
        return self.filter(
            state__gt=SessionState.COMPLETED,
            drop__start_time__lte=timezone.now(),
            drop__end_time__gte=timezone.now(),
        )

    def completed_sessions(self):
        return self.filter(
            state=SessionState.COMPLETED,
            drop__start_time__lte=timezone.now(),
            drop__end_time__gte=timezone.now(),
        )

    def sold_sessions(self):
        return self.filter(state__in=(SessionState.ALLOW_CONTACT_REQUESTED, SessionState.COMPLETED),
                           drop__start_time__lte=timezone.now(),
                           drop__end_time__gte=timezone.now())


class DropSessionManager(models.Manager.from_queryset(DropSessionQuerySet)):
    """Manager for all current drop sessions with active drops"""
    pass


class DropSession(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="drop_sessions")
    drop = models.ForeignKey(Drop, on_delete=models.CASCADE, related_name="drop_sessions")
    state = models.IntegerField(choices=SessionState.choices, default=SessionState.READY)
    manual_override = models.BooleanField(default=False)
    bonus_coin_claimed = models.ForeignKey(
        BonusCoin, on_delete=models.SET_NULL, default=None, blank=True, null=True, related_name="drop_sessions"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    ## Managers to find sessions at different states
    objects = DropSessionManager()

    class Meta:
        unique_together = ('customer', 'drop')
        ordering = ('-state', '-updated')

    def is_active(self) -> bool:
        return self.state < SessionState.COMPLETED and (self.drop.start_time < timezone.now() < self.drop.end_time)

    def __str__(self):
        return f"{self.drop.name}"


class MessageDirection(models.IntegerChoices):
    RECEIVED = 0, 'received'
    SENT = 1, 'sent'


class OrderStatus(models.IntegerChoices):
    STARTED = 0, 'started'
    CONFIRMED = 1, 'confirmed'
    SHIPPED = 2, 'shipped'
    CANCELLED = 3, 'cancelled'


class OrderQuerySet(models.QuerySet):
    def active_orders(self) -> models.QuerySet:
        return self.filter(status__lt=OrderStatus.CANCELLED)


class OrdersManager(models.Manager):
    def get_queryset(self) -> models.QuerySet:
        return OrderQuerySet(
            model=self.model,
            using=self._db,
            hints=self._hints
        ).active_orders()


class Order(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, db_index=True, related_name="orders")
    drop_session = models.OneToOneField(DropSession, on_delete=models.CASCADE, db_index=True, blank=False, null=False,
                                        related_name='order')
    sku = models.ForeignKey(Sku, on_delete=models.CASCADE, related_name="orders", db_index=True)
    date = models.DateTimeField(auto_now_add=True)
    shipping_address = models.TextField(default=None, blank=True, null=True)
    shipping_name = models.TextField(default=None, blank=True, null=True)
    status = models.IntegerField(default=OrderStatus.STARTED, choices=OrderStatus.choices, db_index=True)
    conversion_rate_mob_to_currency = models.FloatField(default=0.0)

    active_orders = OrdersManager()
    objects = models.Manager()

    def cancel(self):
        self.status = OrderStatus.CANCELLED
        self.save()


class PaymentStatus(models.TextChoices):
    FAILURE = "Failure"
    PENDING = "TransactionPending"
    SUCCESS = "TransactionSuccess"


class PaymentManager(models.Manager):
    def create_from_signal(self, message: SignalMessage, mcc: "mobot_client.payments.MCClient", callback: Optional[Callable]) -> Payment:
        return mcc.process_receipt(message.source, message.payment.receipt, callback)


class Payment(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='payments')
    amount_pmob = models.PositiveIntegerField(null=False, blank=False)
    receipt = models.TextField(default=None, blank=True, null=True, help_text="Full-service receipt")
    created_at = models.DateTimeField(auto_now_add=True)
    processed = models.DateTimeField(blank=True, null=True, help_text="The date a payment was processed, if it was.")
    last_updated = models.DateTimeField(auto_now=True, help_text="Time of last update")
    status = models.SmallIntegerField(choices=PaymentStatus.choices, default=PaymentStatus.PENDING, help_text="Status of payment")
    ### Custom Manager that adds a thread to check status ###
    objects = PaymentManager()


class MessageStatus(models.IntegerChoices):
    ERROR = -1
    NOT_PROCESSED = 0
    PROCESSING = 1
    PROCESSED = 2


class MessageQuerySet(models.QuerySet):
    def not_processing(self) -> models.QuerySet:
        return self.filter(status=MessageStatus.NOT_PROCESSED, direction=MessageDirection.RECEIVED).order_by('date', '-payment').all()

    @transaction.atomic
    def get_message(self):
        if message := self.not_processing().select_for_update().first():
            message.status = MessageStatus.PROCESSING
            message.processing = timezone.now()
            message.save()
            return message


class MessageManager(models.Manager.from_queryset(MessageQuerySet)):
    def create_from_signal(self, store: Store, mcc: "mobot_client.payments.MCClient", customer: Customer, message: SignalMessage, callback: Optional[Callable] = None) -> Message:
        if isinstance(message.source, dict):
            source = message.source['number']
        else:
            source = message.source

        payment = None
        if message.payment:
            payment = Payment.objects.create_from_signal(message, mcc, callback)
        dt = timezone.make_aware(datetime.fromtimestamp(message.timestamp))
        message = self.get_queryset().create(
            customer=customer,
            text=message.text,
            date=dt,
            direction=MessageDirection.RECEIVED,
            payment=payment,
            store=store,
        )
        return message


class Message(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="messages")
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    text = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    status = models.SmallIntegerField(choices=MessageStatus.choices, default=MessageStatus.NOT_PROCESSED)
    processing = models.DateTimeField(blank=True, null=True, help_text="The time we started processing a message")
    processed = models.DateTimeField(blank=True, db_index=True, null=True, help_text="The time at which a message was finished processing")
    direction = models.PositiveIntegerField(choices=MessageDirection.choices, db_index=True)
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, null=True, blank=True, help_text="Attached payment, if it exists", related_name='message')

    ### Custom manager to create from signal and process payment ###
    objects = MessageManager()

    class Meta:
        ordering = ['date', '-payment', '-processing', 'processed']

    def __str__(self):
        text_oneline = self.text.replace("\n", " ||| ")
        return f'Message: customer: {self.customer} - {self.direction} --- {text_oneline}'


class ProcessingError(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE)
    text = models.TextField()


class MobotResponse(models.Model):
    """The response to an incoming message or payment"""
    incoming_message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='responses', null=True, blank=True)
    incoming_payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='responses', null=True, blank=True)
    response_message = models.OneToOneField(Message, on_delete=models.CASCADE, null=True, blank=True, related_name='response')
    response_payment = models.OneToOneField(Payment, on_delete=models.CASCADE, null=True, blank=True, related_name='response')
    created_at = models.DateTimeField(auto_now_add=True)


# ------------------------------------------------------------------------------------------


class SingletonModel(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.pk = 1
        super(SingletonModel, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj


class ChatbotSettings(SingletonModel):
    store = models.ForeignKey(Store, null=True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=255)
    avatar_filename = models.CharField(max_length=255)

    def __str__(self):
        return "Global settings"
