from django.db import models
from django.conf import settings
from phonenumber_field.modelfields import PhoneNumberField
from django.contrib.postgres.fields import ArrayField

from mobot.apps.common.models import BaseMCModel
from mobot.apps.signald_client import Signal
from mobot.apps.payment_service import Payment


class User(BaseMCModel):
    phone_number = PhoneNumberField(primary_key=True)
    name = models.TextField()

    def __str__(self):
        return f'{self.phone_number}'

    def signal_payments_enabled(self, signal: Signal) -> bool:
        signal_profile = signal.get_profile_from_phone_number(self.phone_number)


class Customer(User):
    received_sticker_pack = models.BooleanField(default=False)




class Merchant(User):
    @property
    def account_id(self):
        return settings.ACCOUNT_ID


class Store(BaseMCModel):
    name = models.TextField()
    phone_number = PhoneNumberField()
    description = models.TextField()
    privacy_policy_url = models.TextField()

    def __str__(self):
        return f'{self.name} ({self.phone_number})'


class Item(BaseMCModel):
    store_ref = models.ForeignKey(Store, on_delete=models.CASCADE)
    name = models.TextField()
    description = models.TextField(default=None, blank=True, null=True)
    short_description = models.TextField(default=None, blank=True, null=True)
    image_link = models.TextField(default=None, blank=True, null=True)

    def __str__(self):
        return f'{self.name}'


class Product(BaseMCModel):
    store_ref = models.ForeignKey(Store, on_delete=models.CASCADE)
    item_ref = models.ForeignKey(Item, on_delete=models.CASCADE)
    number_restriction = ArrayField(models.TextField(blank=False, null=False), unique=True, blank=True)

    def __str__(self):
        return f'{self.store.name} - {self.item.name}'


class Validation(BaseMCModel):
    validation_class = models.TextField()



class Drop(Product):
    pre_drop_description = models.TextField()
    advertisement_start_time = models.DateTimeField()
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    def __str__(self):
        return f'{self.store.name} - {self.item.name}'


class Airdrop(Drop):
    amount = models.FloatField()


class Customer(User):
    received_sticker_pack = models.BooleanField(default=False)
    
    def __str__(self):
        return f'{self.phone_number}'


class CustomerStorePreferences(BaseMCModel):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    store_ref = models.ForeignKey(Store, on_delete=models.CASCADE)
    allows_contact = models.BooleanField()
    allows_payment = models.BooleanField()


class Session(BaseMCModel):

    class SessionState(models.IntegerChoices):
        COMPLETED = -1
        STARTED = 0
        ALLOW_CONTACT_REQUESTED = 1
        EXPIRED = 2

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    product_ref = models.ForeignKey(Product, on_delete=models.CASCADE)
    state = models.IntegerField(default=0, choices=SessionState.choices)


class DropSession(Session):
    pass


class Message(BaseMCModel):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    store_ref = models.ForeignKey(Store, on_delete=models.CASCADE)
    text = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    direction = models.PositiveIntegerField()