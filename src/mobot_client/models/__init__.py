#  Copyright (c) 2021 MobileCoin. All rights reserved.

from __future__ import annotations
import random
from decimal import Decimal
from typing import Optional, Union
import logging

from django.db import models
from django.db.models import F, BooleanField, ExpressionWrapper, Q, Case, When, Value
from django.utils import timezone
from django.utils.functional import cached_property
from django.db import transaction
from django.conf import settings
from phonenumber_field.modelfields import PhoneNumberField

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
        return super().get_queryset().annotate(
            number_ordered=models.Count('orders'),
            available=F('quantity') - models.Count('orders')).filter(available__gt=0)


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



    num_available = property(number_available)

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
    currency_symbol = models.CharField(default="$", max_length=1)
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
        return sum(map(lambda coin: coin.number_available_at_start, self.bonus_coins.all()))

    def num_initial_sent(self) -> int:
        return self.drop_sessions(manager='initial_coin_sent_sessions').count()

    def initial_pmob_disbursed(self) -> int:
        return self.num_initial_sent() * self.initial_coin_amount_pmob

    def coins_available(self) -> Union[int, str]:
        if self.drop_type == DropType.AIRDROP:
            return self.initial_coin_limit - self.num_initial_sent()
        else:
            return "N/A"

    # Added for Admin panel
    num_coins_remaining = property(coins_available)

    def under_quota(self) -> bool:
        if self.drop_type == DropType.AIRDROP:
            DropManager.logger.debug("Checking if there are coins available to give out...")
            active_drop_sessions_count = self.drop_sessions(manager='initial_coin_sent_sessions').count()
            DropManager.logger.debug(
                f"There are {active_drop_sessions_count} sessions on this airdrop with an initial limit of {self.initial_coin_limit}"
            )
            return active_drop_sessions_count < self.initial_coin_limit and self.coins_available() > 0
        else:
            return len(self.item.skus) > 0

    def is_active(self) -> bool:
        if self.start_time and self.end_time:
            return self.start_time < timezone.now() < self.end_time
        else:
            return False

    # Added fo admin panel
    currently_active = property(is_active)

    def __str__(self):
        return f"{self.store.name}-{self.name} - {self.start_time}-{self.end_time}"


class BonusCoinManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset() \
            .annotate(
            num_active_sessions=models.Count('drop_sessions', filter=Q(drop_sessions__state__gt=SessionState.READY))) \
            .filter(num_active_sessions__lt=F('number_available_at_start')) \
            .annotate(remaining=F('number_available_at_start') - F('num_active_sessions'))

    @transaction.atomic()
    def claim_random_coin(self, drop_session):
        coins_available = self.get_queryset().select_for_update().filter(drop=drop_session.drop)
        if coins_available.count() > 0:
            coins_dist = [coin.number_remaining() for coin in coins_available]
            coin = random.choices(list(coins_available), weights=coins_dist)[0]
            drop_session.bonus_coin_claimed = coin
            if drop_session.customer.has_store_preferences(drop_session.drop.store):
                drop_session.state = SessionState.COMPLETED
            else:
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

    objects = models.Manager()
    # Manager that annotates available coins
    available = BonusCoinManager()

    def __str__(self):
        return f"BonusCoin ({self.amount_pmob} PMOB)"

    def number_remaining(self) -> int:
        return self.number_available_at_start - self.drop_sessions(manager='sold_sessions').count()

    # Add as read-only property for Admin
    num_remaining = property(number_remaining)

    def number_claimed(self) -> int:
        return self.number_available_at_start - self.number_remaining()

    # Add as read-only property for Admin
    num_claimed = property(number_claimed)


class Customer(models.Model):
    phone_number = PhoneNumberField(db_index=True, unique=True)
    received_sticker_pack = models.BooleanField(default=False)

    def matches_country_code_restriction(self, drop: Drop) -> bool:
        return f"+{self.phone_number.country_code}" == drop.number_restriction

    def active_drop_sessions(self):
        return self.drop_sessions(manager='active_sessions').all()

    @property
    def has_active_drop_session(self) -> bool:
        return self.drop_sessions.count() > 0

    def sessions_awaiting_payment(self):
        return self.active_drop_sessions().filter(state=SessionState.WAITING_FOR_PAYMENT)

    @property
    def has_sessions_awaiting_payment(self):
        return self.sessions_awaiting_payment().count() > 0

    def completed_drop_sessions(self):
        return self.drop_sessions(manager='completed_sessions').all()

    def errored_sessions(self):
        return self.drop_sessions(manager='errored_sessions').all()

    def successful_sessions(self):
        '''Return customer sessions with a sale completed'''
        return self.drop_sessions(manager='sold_sessions').all()

    def has_completed_drop(self, drop: Drop) -> bool:
        completed_drop = self.completed_drop_sessions().filter(drop=drop).first()
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


class CustomerDropRefunds(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="drop_refunds", db_index=True)
    drop = models.ForeignKey(Drop, on_delete=models.CASCADE, related_name="drop_refunds", db_index=True)
    number_of_times_refunded = models.PositiveIntegerField(default=0)


class ActiveDropSessionManager(models.Manager):
    """Manager for all current drop sessions with active drops"""
    def get_queryset(self) -> models.QuerySet:
        return super().get_queryset().filter(state__lt=SessionState.COMPLETED,
                                             state__gte=SessionState.READY,
                                             drop__start_time__lte=timezone.now(),
                                             drop__end_time__gte=timezone.now())


class InitialCoinSentDropSessionManager(models.Manager):
    def get_queryset(self) -> models.QuerySet:
        return super().get_queryset().filter(state__gt=SessionState.READY,
                                             drop__start_time__lte=timezone.now(),
                                             drop__end_time__gte=timezone.now())


class ErroredDropSessionManager(models.Manager):
    def get_queryset(self) -> models.QuerySet:
        return super().get_queryset().filter(state__gt=SessionState.COMPLETED)


class CompletedDropSessionManager(models.Manager):
    def get_queryset(self) -> models.QuerySet:
        return super().get_queryset().filter(state=SessionState.COMPLETED)

class SaleCompleteDropSessionManager(models.Manager):
    def get_queryset(self) -> models.QuerySet:
        return super().get_queryset().filter(state__in=(SessionState.ALLOW_CONTACT_REQUESTED, SessionState.COMPLETED))


class DropSession(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="drop_sessions")
    drop = models.ForeignKey(Drop, on_delete=models.CASCADE, related_name="drop_sessions")
    state = models.IntegerField(choices=SessionState.choices, default=SessionState.READY)
    manual_override = models.BooleanField(default=False)
    bonus_coin_claimed = models.ForeignKey(
        BonusCoin, on_delete=models.SET_NULL, default=None, blank=True, null=True, related_name="drop_sessions"
    )
    created_at = models.DateTimeField(default=timezone.now)

    ## Managers to find sessions at different states
    objects = models.Manager()
    active_sessions = ActiveDropSessionManager()
    initial_coin_sent_sessions = InitialCoinSentDropSessionManager()
    errored_sessions = ErroredDropSessionManager()
    sold_sessions = SaleCompleteDropSessionManager()
    completed_sessions = CompletedDropSessionManager()

    class Meta:
        base_manager_name = 'active_sessions'

    def is_active(self) -> bool:
        return self.state < SessionState.COMPLETED and (self.drop.start_time < timezone.now() < self.drop.end_time)

    def __str__(self):
        return f"{self.drop.name}:{self.drop.drop_type}:{self.created_at} - {self.customer.phone_number.as_e164}"


class MessageDirection(models.IntegerChoices):
    RECEIVED = 0, 'received'
    SENT = 1, 'sent'


class Message(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="messages")
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    text = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    direction = models.PositiveIntegerField(choices=MessageDirection.choices)


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
