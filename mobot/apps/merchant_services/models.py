from django.db import models
from django.conf import settings
from phonenumber_field.modelfields import PhoneNumberField
from django.contrib.postgres.fields import ArrayField


class BaseModel(models.Model):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)



class User(BaseModel):
    phone_number = PhoneNumberField(primary_key=True)
    name = models.TextField()

    def __str__(self):
        return f'{self.phone_number}'


class Customer(User):
    received_sticker_pack = models.BooleanField(default=False)


class Merchant(User):
    @property
    def account_id(self):
        return settings.ACCOUNT_ID


class Store(BaseModel):
    name = models.TextField()
    phone_number = PhoneNumberField()
    description = models.TextField()
    privacy_policy_url = models.TextField()

    def __str__(self):
        return f'{self.name} ({self.phone_number})'


class Item(BaseModel):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    name = models.TextField()
    description = models.TextField(default=None, blank=True, null=True)
    short_description = models.TextField(default=None, blank=True, null=True)
    image_link = models.TextField(default=None, blank=True, null=True)

    def __str__(self):
        return f'{self.name}'


class Product(BaseModel):

    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    number_restriction = ArrayField(models.TextField(blank=False, null=False), unique=True, blank=True)

    def __str__(self):
        return f'{self.store.name} - {self.item.name}'


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


class CustomerStorePreferences(BaseModel):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    allows_contact = models.BooleanField()
    allows_payment = models.BooleanField()


class Session(BaseModel):

    class SessionState(models.IntegerChoices):
        COMPLETED = -1
        STARTED = 0
        ALLOW_CONTACT_REQUESTED = 1
        EXPIRED = 2

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    state = models.IntegerField(default=0, choices=SessionState.choices)


class DropSession(Session):
    pass


class CustomerStorePreferences(BaseModel):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    allows_contact = models.BooleanField()


class Message(BaseModel):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    text = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    direction = models.PositiveIntegerField()