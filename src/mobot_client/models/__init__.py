#  Copyright (c) 2021 MobileCoin. All rights reserved.

import random
from decimal import Decimal
from typing import Optional

from django.db import models
from django.db.models import F, BooleanField, ExpressionWrapper, Q
from django.utils import timezone
from django.db import transaction

from mobot_client.models.states import SessionState
from mobot_client.models.phone_numbers import PhoneNumberField


import mobilecoin as mc

from mobot_client.models.states import SessionState


class Store(models.Model):
    name = models.TextField()
    phone_number = PhoneNumberField(db_index=True)
    description = models.TextField()
    privacy_policy_url = models.URLField()

    def __str__(self):
        return f"{self.name} ({self.phone_number})"


class Item(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="items")
    name = models.TextField()
    price_in_pmob = models.PositiveIntegerField(default=None, blank=True, null=True)
    description = models.TextField(default=None, blank=True, null=True)
    short_description = models.TextField(default=None, blank=True, null=True)
    image_link = models.URLField(default=None, blank=True, null=True)

    @property
    def price_in_mob(self) -> Decimal:
        return mc.pmob2mob(self.price_in_pmob)

    def available_skus(self) -> models.QuerySet:
        return self.skus.filter(available__gt=0)

    def __str__(self):
        return f"{self.name}"


class AvailableSkuManager(models.Manager):
    def get_queryset(self) -> models.QuerySet:
        return super().get_queryset().annotate(
            number_ordered=models.Count('orders'),
            available=F('quantity') - models.Count('orders')
        )


class Sku(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="skus")
    identifier = models.TextField()
    quantity = models.PositiveIntegerField(default=0)
    sort_order = models.PositiveIntegerField(default=0)

    available = AvailableSkuManager()
    objects = models.Manager()

    class Meta:
        unique_together = ('item', 'identifier')
        base_manager_name = 'available'

    def __str__(self) -> str:
        return f"{self.item.name} - {self.identifier}"

    def number_available(self) -> int:
        return self.quantity - self.orders.count()

    def in_stock(self) -> bool:
        return self.number_available() > 0


class DropType(models.IntegerChoices):
    AIRDROP = 0, 'airdrop'
    ITEM = 1, 'item'


class DropQuerySet(models.QuerySet):
    def advertising_drops(self) -> models.QuerySet:
        return self.filter(
            dvertisment_start_time__lte=timezone.now(),
            start_time__gt=timezone.now()
        )

    def active_drops(self) -> models.QuerySet:
        return self.filter(
            start_time__lte=timezone.now(),
            end_time__gte=timezone.now()
        )


class DropManager(models.Manager.from_queryset(DropQuerySet)):
    def advertising_drops(self) -> DropQuerySet:
        return self.get_queryset().advertising_drops()

    def get_advertising_drop(self):
        return self.advertising_drops().first()

    def active_drops(self) -> DropQuerySet:
        return self.get_queryset().active_drops()

    def get_active_drop(self):
        return self.active_drops().first()


class Drop(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='drops')
    drop_type = models.IntegerField(choices=DropType.choices, default=DropType.AIRDROP, db_index=True)
    pre_drop_description = models.TextField()
    advertisment_start_time = models.DateTimeField(db_index=True)
    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField(db_index=True)
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='drops', db_index=True, null=True, blank=True)
    number_restriction = models.TextField(default="+44")
    timezone = models.TextField(default="UTC")
    initial_coin_amount_pmob = models.PositiveIntegerField(default=0)
    initial_coin_limit = models.PositiveIntegerField(default=0)
    conversion_rate_mob_to_currency = models.FloatField(default=1.0)
    currency_symbol = models.TextField(default="$")
    country_code_restriction = models.TextField(default="GB")
    country_long_name_restriction = models.TextField(default="United Kingdom")
    max_refund_transaction_fees_covered = models.PositiveIntegerField(default=0)

    objects = DropManager()

    class Meta:
        base_manager_name = 'objects'

    def clean(self):
        assert self.start_time < self.end_time

    def value_in_currency(self, amount: Decimal) -> Decimal:
        return amount * Decimal(self.conversion_rate_mob_to_currency)

    def under_quota(self) -> bool:
        if self.drop_type == DropType.AIRDROP:
            return self.drop_sessions.count() < self.initial_coin_limit
        else:
            return True

    def __str__(self):
        return f"{self.store.name} - {self.item.name}"


class BonusCoinManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset()\
            .annotate(num_active_sessions=models.Count('drop_sessions', filter=Q(drop_sessions__state__gt=SessionState.READY))) \
            .filter(num_active_sessions__lt=F('number_available_at_start'))

    @transaction.atomic()
    def claim_random_coin(self, drop_session) -> Optional['mobot_client.models.BonusCoin']:
        coins_available = self.get_queryset().select_for_update().filter(drop=drop_session.drop)
        if coins_available.count() > 0:
            coin = random.choice(list(coins_available))
            drop_session.bonus_coin_claimed = coin
            drop_session.state = SessionState.WAITING_FOR_PAYMENT_OR_BONUS_TX
            drop_session.save()
            return coin
        else:
            return None


class BonusCoin(models.Model):
    drop = models.ForeignKey(Drop, on_delete=models.CASCADE, related_name='bonus_coins', db_index=True)
    amount_pmob = models.PositiveIntegerField(default=0)
    number_available_at_start = models.PositiveIntegerField(default=0)

    available = BonusCoinManager()

    class Meta:
        base_manager_name = 'available'

    def __str__(self):
        return f"BonusCoin {self.pk} ({self.amount_pmob} PMOB)"

    def number_remaining(self) -> int:
        return self.number_available_at_start - self.drop_sessions(manager='active_sessions').count()

    def number_claimed(self) -> int:
        return self.number_available_at_start - self.number_remaining()


class Customer(models.Model):
    phone_number = PhoneNumberField(db_index=True)
    received_sticker_pack = models.BooleanField(default=False)

    def has_completed_drop(self, drop: Drop) -> bool:
        self.drop_sessions.filter(drop=drop, state=SessionState.COMPLETED).first() is not None

    def __str__(self):
        return f"{self.phone_number}"


class CustomerStorePreferences(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="customer_store_preferences", db_index=True)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="customer_store_preferences", db_index=True)
    allows_contact = models.BooleanField()


class CustomerDropRefunds(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="drop_refunds", db_index=True)
    drop = models.ForeignKey(Drop, on_delete=models.CASCADE, related_name="drop_refunds", db_index=True)
    number_of_times_refunded = models.PositiveIntegerField(default=0)


class ActiveOrCompletedManager(models.Manager):
    def get_queryset(self) -> models.QuerySet:
        return super().get_queryset().filter(state__gt=SessionState.READY)


class ActiveDropSessionManager(ActiveOrCompletedManager):
    def get_queryset(self) -> models.QuerySet:
        return super().get_queryset().filter(state__lt=SessionState.COMPLETED)


class RefundableDropSessionManager(models.Manager):
    def get_queryset(self) -> models.QuerySet:
        return super().get_queryset().filter(state__in=SessionState.refundable_states)


class DropSession(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="drop_sessions")
    drop = models.ForeignKey(Drop, on_delete=models.CASCADE, related_name="drop_sessions")
    state = models.IntegerField(choices=SessionState.choices, default=SessionState.READY)
    manual_override = models.BooleanField(default=False)
    bonus_coin_claimed = models.ForeignKey(
        BonusCoin, on_delete=models.CASCADE, default=None, blank=True, null=True, related_name="drop_sessions"
    )
    ## Managers to find sessions at different states
    objects = models.Manager()
    active_sessions = ActiveDropSessionManager()
    active_or_completed_sessions = ActiveOrCompletedManager()
    refundable_sessions = RefundableDropSessionManager()

    def under_quota(self) -> bool:
        return self.bonus_coin_claimed.number_remaining() > 0


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
    def __init__(self, sku: Sku = None, active: bool = True, *args, **kwargs):
        self._sku = sku
        self._active = active
        super().__init__(*args, **kwargs)

    def get_queryset(self) -> models.QuerySet:
        return OrderQuerySet(
            model=self.model,
            using=self._db,
            hints=self._hints
        ).active_orders()


class Order(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, db_index=True, related_name="orders")
    drop_session = models.OneToOneField(DropSession, on_delete=models.CASCADE, db_index=True,  blank=False, null=False, related_name='order')
    sku = models.ForeignKey(Sku, on_delete=models.CASCADE, related_name="orders", db_index=True)
    date = models.DateTimeField(auto_now_add=True)
    shipping_address = models.TextField(default=None, blank=True, null=True)
    shipping_name = models.TextField(default=None, blank=True, null=True)
    status = models.IntegerField(default=0, choices=OrderStatus.choices, db_index=True)
    conversion_rate_mob_to_currency = models.FloatField(default=0.0)

    active_orders = OrdersManager(None, True)
    objects = models.Manager()

    class Meta:
        base_manager_name = 'active_orders'


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
    name = models.TextField()
    avatar_filename = models.TextField()

    def __str__(self):
        return "Global settings"


class Payment(models.Model):
    class PaymentType(models.IntegerChoices):
        REFUND = -2, 'refund'
        BONUS = -1, 'bonus'
        PAYMENT = 1, 'payment'

    class PaymentDirection(models.IntegerChoices):
        TO_CUSTOMER = -1, 'to_customer'
        TO_STORE = 1, 'to_store'

    class PaymentStatus(models.IntegerChoices):
        NOT_STARTED = -3, 'not_started'
        FAILURE = -2, 'failure'
        NO_ADDRESS = -1, 'no address found for customer'
        IN_PROGRESS = 0, 'in progress'
        SUCCEEDED = 1, 'succeeded'
        NOT_NECESSARY = 2, 'empty because amount in mob was too small to send'

    drop_session = models.ForeignKey(DropSession, related_name='payments', null=True, blank=True, on_delete=models.CASCADE)
    payment_type = models.IntegerField(choices=PaymentType.choices, db_index=True, null=True, blank=True)
    amount_in_mob = models.DecimalField(db_index=True, max_length=16, decimal_places=6, max_digits=6, default=Decimal(0))
    direction = models.IntegerField(choices=PaymentDirection.choices, default=PaymentDirection.TO_STORE)
    status = models.IntegerField(choices=PaymentStatus.choices, default=PaymentStatus.NOT_STARTED)
    payment_address = models.TextField(blank=True, null=True)





