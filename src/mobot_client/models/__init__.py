#  Copyright (c) 2021 MobileCoin. All rights reserved.

from decimal import Decimal

from django.db import models
import mobilecoin as mc

from mobot_client.models.states import SessionState


class Store(models.Model):
    name = models.TextField()
    phone_number = models.TextField(db_index=True)
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


class Sku(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="skus")
    identifier = models.TextField()
    quantity = models.PositiveIntegerField(default=0)
    sort_order = models.PositiveIntegerField(default=0)


class DropType(models.IntegerChoices):
    AIRDROP = 0, 'airdrop'
    ITEM = 1, 'item'


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

    def __str__(self):
        return f"{self.store.name} - {self.item.name}"


class BonusCoin(models.Model):
    drop = models.ForeignKey(Drop, on_delete=models.CASCADE, related_name='bonus_coins', db_index=True)
    amount_pmob = models.PositiveIntegerField(default=0)
    number_available_at_start = models.PositiveIntegerField(default=0)


class Customer(models.Model):
    phone_number = models.TextField(db_index=True)
    received_sticker_pack = models.BooleanField(default=False)

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


class DropSession(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="drop_sessions")
    drop = models.ForeignKey(Drop, on_delete=models.CASCADE, related_name="drop_sessions")
    state = models.IntegerField(choices=SessionState.choices, default=SessionState.READY)
    manual_override = models.BooleanField(default=False)
    bonus_coin_claimed = models.ForeignKey(
        BonusCoin, on_delete=models.CASCADE, default=None, blank=True, null=True, related_name="drop_sessions"
    )


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


class Order(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, db_index=True, related_name="orders")
    drop_session = models.OneToOneField(DropSession, on_delete=models.CASCADE, db_index=True,  blank=False, null=False, related_name='order')
    sku = models.ForeignKey(Sku, on_delete=models.CASCADE, related_name="orders", db_index=True)
    date = models.DateTimeField(auto_now_add=True)
    shipping_address = models.TextField(default=None, blank=True, null=True)
    shipping_name = models.TextField(default=None, blank=True, null=True)
    status = models.IntegerField(default=0, choices=OrderStatus.choices, db_index=True)
    conversion_rate_mob_to_currency = models.FloatField(default=0.0)


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
