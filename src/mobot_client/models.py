# Copyright (c) 2021 MobileCoin. All rights reserved.
import enum

from django.db import models


class SessionState(models.IntegerChoices):
    OUT_OF_MOB = -2
    CANCELLED = -1
    READY_TO_RECEIVE_INITIAL = 0
    WAITING_FOR_BONUS_TRANSACTION = 1
    ALLOW_CONTACT_REQUESTED = 2
    COMPLETED = 3


class Store(models.Model):
    name = models.TextField()
    phone_number = models.TextField()
    description = models.TextField()
    privacy_policy_url = models.TextField()

    def __str__(self):
        return f"{self.name} ({self.phone_number})"


class Item(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    name = models.TextField()
    price_in_pmob = models.PositiveIntegerField(default=None, blank=True, null=True)
    description = models.TextField(default=None, blank=True, null=True)
    short_description = models.TextField(default=None, blank=True, null=True)
    image_link = models.TextField(default=None, blank=True, null=True)

    def __str__(self):
        return f"{self.name}"


class Sku(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    identifier = models.TextField()
    quantity = models.PositiveIntegerField(default=0)
    sort_order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.item.name} - {self.identifier}"


class DropType(models.IntegerChoices):
    AIRDROP = 0, 'airdrop'
    ITEM = 1, 'item'


class Drop(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    drop_type = models.IntegerField(choices=DropType.choices, default=DropType.AIRDROP)
    pre_drop_description = models.TextField()
    advertisment_start_time = models.DateTimeField()
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    number_restriction = models.TextField()
    timezone = models.TextField()
    initial_coin_amount_pmob = models.PositiveIntegerField(default=0)
    initial_coin_limit = models.PositiveIntegerField(default=0)
    conversion_rate_mob_to_currency = models.FloatField(default=1.0)
    currency_symbol = models.TextField(default="$")
    country_code_restriction = models.TextField(default="GB")
    country_long_name_restriction = models.TextField(default="United Kingdom")
    max_refund_transaction_fees_covered = models.PositiveIntegerField(default=0)

    def value_in_currency(self, amount):
        return amount * self.conversion_rate_mob_to_currency

    def __str__(self):
        return f"{self.store.name} - {self.item.name}"


class BonusCoin(models.Model):
    drop = models.ForeignKey(Drop, on_delete=models.CASCADE)
    amount_pmob = models.PositiveIntegerField(default=0)
    number_available = models.PositiveIntegerField(default=0)


class Customer(models.Model):
    phone_number = models.TextField(primary_key=True)
    received_sticker_pack = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.phone_number}"


class CustomerStorePreferences(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    allows_contact = models.BooleanField()


class CustomerDropRefunds(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    drop = models.ForeignKey(Drop, on_delete=models.CASCADE)
    number_of_times_refunded = models.PositiveIntegerField(default=0)


class DropSession(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    drop = models.ForeignKey(Drop, on_delete=models.CASCADE)
    state = models.IntegerField(choices=SessionState.choices, default=SessionState.READY_TO_RECEIVE_INITIAL)
    manual_override = models.BooleanField(default=False)
    bonus_coin_claimed = models.ForeignKey(
        BonusCoin, on_delete=models.CASCADE, default=None, blank=True, null=True
    )


class MessageDirection(models.IntegerChoices):
    RECEIVED = 0, 'received'
    SENT = 1, 'sent'


class Message(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    text = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    direction = models.PositiveIntegerField(choices=MessageDirection.choices)


class Order(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    drop_session = models.ForeignKey(DropSession, on_delete=models.CASCADE)
    sku = models.ForeignKey(Sku, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)
    shipping_address = models.TextField(default=None, blank=True, null=True)
    shipping_name = models.TextField(default=None, blank=True, null=True)
    status = models.IntegerField(default=0)
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
