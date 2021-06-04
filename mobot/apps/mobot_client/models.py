import phonenumbers
from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.postgres.fields import ArrayField
from typing import TypeVar, Generic, Callable, Set
import datetime
import pytz
# Create your models here.
from django.db import models
from uuid import uuid4
from phonenumber_field.modelfields import PhoneNumberField


class BaseModel(models.Model): ...


class Store(BaseModel):
    name = models.TextField()
    store_number = models.TextField(primary_key=True, default=uuid4())
    description = models.TextField()
    privacy_policy_url = models.TextField()

    def __str__(self):
        return f'{self.name} ({self.phone_number})'

class SignalStore(Store):
    phone_number = models.TextField(blank=False)
    store_number = PhoneNumberField(default=phone_number)

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
    timezone = models.TextField()
    number_restriction = models.TextChoices()

    def __str__(self):
        return f'{self.store.name} - {self.item.name}'


class Drop(Product):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    pre_drop_description = models.TextField()
    advertisement_start_time = models.DateTimeField()
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    timezone = models.TextField()

    def __str__(self):
        return f'{self.store.name} - {self.item.name}'


class Airdrop(Drop):
    amount = models.FloatField()



class Customer(BaseModel):
    phone_number = models.TextField(primary_key=True)
    received_sticker_pack = models.BooleanField(default=False)
    
    def __str__(self):
        return f'{self.phone_number}'

class CustomerStorePreferences(BaseModel):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    allows_contact = models.BooleanField()
    allows_payment = models.BooleanField()



class ValidationField(models.Field):

    description = "A field used for storing Validations"

    def __init__(self, *args, **kwargs):
        self.validation_name = kwargs['validation_name']
        self.validate_fn: Callable[[*T], bool] = pickle.loads(kwargs['fn'])



class Session(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    drop = models.ForeignKey(Drop, on_delete=models.CASCADE)
    state = models.IntegerField(default=0)




class Validation(BaseModel):
    @staticmethod
    def default_validation(session: Session) -> bool:
        return True
    validation_id: models.AutoField(primary_key=True)
    name: models.TextField(default="SessionValidation")
    fn: models.TextField(default=default_validation, serialize=ValidationFunctionSerializer)






class DropSession(BaseModel):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    drop = models.ForeignKey(Drop, on_delete=models.CASCADE)
    state = models.IntegerField(default=0)
    validations = ArrayField(models.ForeignKey(Validation, on_delete=models.CASCADE))

    def clean(self):
        # Don't allow draft entries to have a pub_date.
        if self.status == 'draft' and self.pub_date is not None:
            raise ValidationError('Draft entries may not have a publication date.')
        # Set the pub_date for published items if it hasn't been set already.
        if self.status == 'published' and self.pub_date is None:
            self.pub_date = datetime.date.today()


class Message(BaseModel):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    text = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    direction = models.PositiveIntegerField()