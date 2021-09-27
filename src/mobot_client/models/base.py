#  Copyright (c) 2021 MobileCoin. All rights reserved.

from __future__ import annotations
import random
from decimal import Decimal
from typing import Optional, Union
import logging

from django.db import models
from django.db.models import F, Sum
from django.utils import timezone
from django.utils.functional import cached_property
from django.db import transaction
from django.contrib import admin
from phonenumber_field.modelfields import PhoneNumberField
from tenacity import wait_random_exponential, retry, retry_if_exception_type

from mobot_client.models.exceptions import ConcurrentModificationException
from mobot_client.models.states import SessionState


logger = logging.getLogger("ModelsLogger")


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
    price_in_mob = models.DecimalField(default=0, decimal_places=8, max_digits=12)
    description = models.TextField(default=None, blank=True, null=True)
    short_description = models.TextField(default=None, blank=True, null=True)
    image_link = models.URLField(default=None, blank=True, null=True)


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
    pre_drop_description = models.TextField(default="MOB")
    advertisment_start_time = models.DateTimeField(db_index=True, default=timezone.now)
    start_time = models.DateTimeField(db_index=True, default=timezone.now)
    end_time = models.DateTimeField(db_index=True, default=timezone.now)
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='drops', db_index=True, null=True, blank=True)
    number_restriction = models.CharField(default="+44", max_length=255, blank=True)
    timezone = models.CharField(default="Europe/London", max_length=255)
    initial_coin_amount_mob = models.DecimalField(decimal_places=8, max_digits=12, default=Decimal(0), verbose_name="Initial mob award amount")
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

    @admin.display(description='Initial Payments')
    def num_initial_sent(self) -> int:
        return DropSession.objects.initial_coin_sent_sessions().filter(drop=self).count()

    @admin.display(description='Bonus Payments')
    def num_bonus_sent(self) -> int:
        return BonusCoin.objects.filter(drop=self).aggregate(Sum('number_claimed'))[
            'number_claimed__sum']

    def bonus_mob_disbursed(self) -> Decimal:
        if self.bonus_coins.count():
            return BonusCoin.objects.with_sum_spent().filter(drop=self).aggregate(Sum('mob_claimed'))[
                'mob_claimed__sum']
        else:
            return Decimal(0)

    def initial_mob_disbursed(self) -> Decimal:
        return Decimal(self.num_initial_sent() * self.initial_coin_amount_mob)

    def initial_coins_available(self) -> Union[int, str]:
        if self.drop_type == DropType.AIRDROP:
            return self.initial_coin_limit - self.num_initial_sent()
        else:
            return "N/A"

    def under_quota(self) -> bool:
        if self.drop_type == DropType.AIRDROP:
            DropManager.logger.info("Checking if there are coins available to give out...")
            active_drop_sessions_count = DropSession.objects.initial_coin_sent_sessions().filter(drop=self).count()
            logger.debug(
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
    def with_sum_spent(self) -> models.QuerySet:
        return self.annotate(mob_claimed=F('number_claimed') * F('amount_mob')).all()

    def available_coins(self) -> models.QuerySet:
        available = self.filter(number_available_at_start__gt=F('number_claimed'))
        return available


class BonusCoinManager(models.Manager.from_queryset(BonusCoinQuerySet)):

    def _claim_optimistic(self, coin: BonusCoin, number_claimed: int):
        """Try to claim a coin using optimistic locking - assume we know the number claimed is the same as it was when we
           entered the transaction, and fail if the update fails
        """
        with transaction.atomic():
            updated = self.available_coins().filter(pk=coin.pk, number_claimed=number_claimed).select_for_update().update(number_claimed=number_claimed + 1)
            if not updated:
                raise ConcurrentModificationException()
        coin.refresh_from_db()
        return coin

    @retry(wait=wait_random_exponential(multiplier=1, min=4, max=10), retry=retry_if_exception_type(ConcurrentModificationException))
    def find_and_claim_unclaimed_coin(self) -> BonusCoin:
        coins_available = self.available_coins()
        coins_dist = [coin.number_remaining() for coin in coins_available]
        if len(coins_available) > 0:
            coin: BonusCoin = random.choices(coins_available, weights=coins_dist)[0]
            if coin.number_remaining() < 1:
                raise ConcurrentModificationException("Coin no longer available; looking for another")
            logger.debug(f"Trying to claim a coin {coin} with number claimed {coin.number_claimed}")
            claimed_coin = self._claim_optimistic(coin, coin.number_claimed)
            logger.info(f"Got a coin! {claimed_coin}")
            claimed_coin.save()
            return claimed_coin
        else:
            raise OutOfStockException("No more bonus coins available to give out!")

    def claim_random_coin_for_session(self, drop_session: DropSession):
        try:
            coin = self.find_and_claim_unclaimed_coin()
            drop_session.bonus_coin_claimed = coin
            drop_session.state = SessionState.ALLOW_CONTACT_REQUESTED
            drop_session.save()
            return coin
        except OutOfStockException as e:
            drop_session.state = SessionState.OUT_OF_STOCK
            drop_session.save()
            raise e


class BonusCoin(models.Model):
    drop = models.ForeignKey(Drop, on_delete=models.CASCADE, related_name='bonus_coins', db_index=True)
    amount_mob = models.DecimalField(default=0, decimal_places=8, max_digits=12)
    number_available_at_start = models.PositiveIntegerField(default=0)
    number_claimed = models.IntegerField(default=0)

    objects = BonusCoinManager()

    def __str__(self):
        return f"BonusCoin ({self.amount_mob} MOB)"

    def number_remaining(self) -> int:
        return self.number_available_at_start - self.number_claimed

    def amount_disbursed(self) -> Decimal:
        return self.number_claimed * self.amount_mob


class Customer(models.Model):
    phone_number = PhoneNumberField(db_index=True, unique=True)
    received_sticker_pack = models.BooleanField(default=False)

    def matches_country_code_restriction(self, drop: Drop) -> bool:
        if not drop.number_restriction.strip():
            return True
        else:
            return f"+{self.phone_number.country_code}" in [s.strip() for s in drop.number_restriction.split(',')]

    def active_drop_sessions(self):
        return DropSession.objects.active_drop_sessions().filter(customer=self)

    @admin.display(description='Active')
    def has_active_drop_session(self) -> bool:
        return self.drop_sessions.count() > 0

    def state(self) -> Optional[SessionState]:
        if active_session := self.active_drop_sessions().first():
            return active_session.get_state_display()
        else:
            return None

    def sessions_awaiting_payment(self):
        return DropSession.objects.awaiting_payment_sessions()

    @admin.display(description='Awaiting Payment')
    def has_session_awaiting_payment(self):
        return self.sessions_awaiting_payment().count() > 0

    has_session_awaiting_payment.short_description = "Awaiting Payment"

    def fulfilled_drop_sessions(self):
        return DropSession.objects.sold_sessions().filter(customer=self)

    @admin.display(description='Fulfilled')
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
        ordering = ('-state', '-updated')

    def is_active(self) -> bool:
        return self.state < SessionState.COMPLETED and (self.drop.start_time < timezone.now() < self.drop.end_time)

    def __str__(self):
        return f"{self.drop.name}"


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
