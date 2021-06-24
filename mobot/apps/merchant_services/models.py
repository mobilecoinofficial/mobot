import datetime
import importlib

from django.db import models
from django.db.models import QuerySet
from django.contrib.auth.models import User
from django.db.models import Q
from mobot.apps.common.models import ClassField
from phonenumber_field.modelfields import PhoneNumberField
from djmoney.models.fields import MoneyField
from typing import TypeVar, List
from moneyed import Money
from mobot.apps.signald_client import Signal
from mobot.apps.payment_service.models import Payment
import logging
from itertools import chain
import inspect
from functools import singledispatchmethod
from django.utils import timezone as tz

T = TypeVar('T', bound=models.Model)


class ValidationTargetManager(models.Manager):
    def _get_queryset(self, validations, base_condition: Q = Q(), target: models.Model = None):
        for validation in validations:
            try:
                logging.warning(f"Adding filter: {validation.q}")
                base_condition.add(validation.q, Q.AND)
            except AttributeError as e:
                logging.exception("Can't get attr")
        return target.objects.filter(base_condition)

    def get_targets(self, validations, campaign_id: str = ""):
        qs = self._get_queryset(validations, target=Customer)
        return qs

class Validation(models.Model):
    model_class_name = models.TextField(db_index=True, blank=False, null=False)
    model_attribute_name = models.TextField(blank=False, null=False)
    comparator_func = models.TextField(blank=False, null=False)
    target_value = models.TextField(blank=False, null=False)
    objects = models.Manager()

    def clean(self):
        if not self.model_class_name.startswith("mobot"):
            self.model_class_name = f"mobot.apps.merchant_services.models.{self.model_class_name}"

    @property
    def _model_class(self):
        try:
            module = importlib.import_module(f"mobot.apps.merchant_services.models")
            return getattr(module, self.model_class_name)
        except ModuleNotFoundError as e:
            logging.exception(f"Unable to find module {__file__}")
            raise e

    @property
    def q(self) -> Q:
        q = Q(**{f"{self.model_attribute_name}__{self.comparator_func}": self.target_value})
        return q

    def __str__(self):
        return f"{self._model_class}::{self.model_attribute_name}{self.comparator_func}={self.target_value}"

class Trackable(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    created_by = models.ForeignKey(User, related_name='created_%(class)s', on_delete=models.DO_NOTHING, null=True, blank=True)
    updated_by = models.ForeignKey(User, related_name='updated_%(class)s', on_delete=models.DO_NOTHING, null=True, blank=True)
    class Meta:
        abstract = True

class ValidatableMixin(Trackable):
    class Meta:
        abstract = True

    targets = ValidationTargetManager()
    objects = models.Manager()
    validations = models.ManyToManyField(Validation)

    @classmethod
    def get_targets(cls, model_id, model_class_name=""):
        validations = cls.objects.filter(id=model_id).first().validations.filter(model_class_name=model_class_name).all()
        cls.targets.get_targets(validations=validations, campaign_id=model_id)


class UserAccount(ValidatableMixin):
    phone_number = PhoneNumberField(primary_key=True)
    name = models.TextField(blank=False, null=False)

    class Meta(ValidatableMixin.Meta):
        app_label = 'merchant_services'
        ordering = ['name']

    def signal_payments_enabled(self, signal: Signal) -> bool:
        signal_profile = signal.get_profile_from_phone_number(self.phone_number)
        try:
            _customer_payments_address = signal_profile['data']['paymentsAddress']
            return True
        except:
            return False

    def payments_address(self, signal: Signal):
        signal_profile = signal.get_profile_from_phone_number(self.phone_number)
        try:
            customer_payments_address = signal_profile['data']['paymentsAddress']
            return customer_payments_address
        except Exception as e:
             logging.exception(str(f"{self.name}:{self.phone_number}"))


class Merchant(UserAccount):
    class Meta(UserAccount.Meta):
        db_table = 'merchant_service_users'
    merchant_description = models.TextField(blank=True, default="A Mobot Merchant")
    objects = models.Manager()


class Customer(UserAccount):
    class Meta(ValidatableMixin.Meta):
        db_table = 'merchant_service_customers'

    received_sticker_pack = models.BooleanField(default=False)
    objects = models.Manager()

class MCStore(Trackable):
    name = models.TextField(blank=True, default="Coin Shop")
    description = models.TextField(blank=True, default="Mobot Store")
    privacy_policy_url = models.URLField(blank=True, default="https://mobilecoin.com/privacy")
    merchant_ref = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="store_owner")

    def __str__(self):
        return f'{self.name}:{self.phone_number}:store'


class Product(Trackable):
    store_ref = models.ForeignKey(MCStore, on_delete=models.CASCADE)
    name = models.TextField(blank=False, null=False)
    description = models.TextField(default="Airdrop: Free mobilecoin!", blank=True, null=True)
    short_description = models.TextField(default="Airdrop", blank=False, null=False)
    image_link = models.URLField(default=None, blank=True, null=True)
    allows_refund = models.BooleanField(default=True, blank=False, null=False)
    price = MoneyField(max_digits=14, decimal_places=5, default_currency='GBP', help_text='Price of the product',
                       blank=False, default=1.0)

    class Meta:
        app_label = 'merchant_services'
        abstract = False
        default_related_name = 'products'


class InventoryItem(models.Model):
    product_ref = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="inventory")


class Campaign(ValidatableMixin):
    name = models.TextField(help_text="Campaign name", null=False, blank=False)
    product_ref = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="campaigns", db_index=True)
    pre_drop_description = models.TextField(default="MobileCoin Product Drop")
    advertisement_start_time = models.DateTimeField(auto_now=True)
    start_time = models.DateTimeField(default=tz.now())
    end_time = models.DateTimeField(default=tz.now() + datetime.timedelta(days=1))
    quota = models.PositiveIntegerField(default=10)
    adjusted_price = MoneyField(max_digits=14, default=None, decimal_places=5, default_currency="PMB", blank=True, null=True)

    def _get_targets(self, model_class):
        return Campaign.get_targets(self.id, model_class_name=model_class)

    def get_target_validations(self, model_class):
        campaign_validations = self._get_targets(model_class)
        return campaign_validations

    def get_target_customers(self):
        customer_validations = self._get_targets(Customer.__name__)
        return customer_validations

    @property
    def price(self) -> Money:
        if self.adjusted_price:
            return self.adjusted_price
        else:
            return self.product_ref.price

    def __str__(self):
        return str(f"Campaign({self.id}, {self.name})")


class Sale(Trackable):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, blank=False, null=False, related_name="sales")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, blank=False, null=False)
    price = MoneyField(blank=False, null=False, max_digits=14)
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="sales")
    campaign = models.ForeignKey(Campaign, on_delete=models.DO_NOTHING, related_name="sales")

    def clean(self):
        if not self.merchant:
            self.merchant = self.product.store_ref.merchant_ref
        self.save()



class CustomerStorePreferences(Trackable):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    store_ref = models.ForeignKey(MCStore, on_delete=models.CASCADE)
    allows_contact = models.BooleanField()


class Message(Trackable):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    store_ref = models.ForeignKey(MCStore, on_delete=models.CASCADE)
    text = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    direction = models.PositiveIntegerField()