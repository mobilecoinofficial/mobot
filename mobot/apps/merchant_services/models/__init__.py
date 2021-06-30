import datetime
import importlib
from dataclasses import dataclass
from enum import Enum

from dataclasses_json import dataclass_json
from django.db import models
from typing import TypeVar
import logging
from django.conf import settings
from django.db.models import Q, QuerySet
from django.utils import timezone as tz
from django_fsm import FSMIntegerField, transition
from djmoney.models.fields import MoneyField
from djmoney.money import Money
from moneyed import Money
from phonenumber_field.modelfields import PhoneNumberField
from address.models import AddressField
from address.models import Address
from django.db.transaction import atomic
from django.utils import timezone as tz


from django.contrib.auth.models import User
from mobot.apps.merchant_services.models.utils import DataclassField
from mobot.apps.signald_client import Signal

T = TypeVar('T', bound=models.Model)


logger = logging.getLogger("MerchantServices")
logger.setLevel(settings.LOG_LEVEL)


class Trackable(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    created_by = models.ForeignKey(User, related_name='created_%(class)s', on_delete=models.DO_NOTHING, null=True,
                                   blank=True)
    updated_by = models.ForeignKey(User, related_name='updated_%(class)s', on_delete=models.DO_NOTHING, null=True,
                                   blank=True)

    class Meta:
        abstract = True


class ValidationTargetManager(models.Manager):
    def _get_queryset(self, validations, base_condition: Q = Q(), target: models.Model = None):
        for validation in validations:
            try:
                logger.warning(f"Adding filter: {validation.q}")
                base_condition.add(validation.q, Q.AND)
            except AttributeError as e:
                logger.exception("Can't get attr")
            except Exception as e:
                logger.exception("Can't add filter")
        qs = target.objects.filter(base_condition).all()
        return qs

    def get_targets(self, validations, target: str) -> QuerySet:
        module = importlib.import_module('mobot.apps.merchant_services.models')
        clz = getattr(module, target)
        qs = self._get_queryset(validations, target=clz)
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
            logger.exception(f"Unable to find module {__file__}")
            raise e

    @property
    def q(self) -> Q:
        q = Q(**{f"{self.model_attribute_name}__{self.comparator_func}": self.target_value})
        return q

    def __str__(self):
        return f"{self._model_class}::{self.model_attribute_name}{self.comparator_func}={self.target_value}"


class ValidatableMixin(Trackable):
    class Meta:
        abstract = True

    targets = ValidationTargetManager()
    objects = models.Manager()
    validations = models.ManyToManyField(Validation)

    @classmethod
    def get_campaign_targets(cls, campaign_id, model_class_name="") -> QuerySet:
        validations = cls.objects.filter(id=campaign_id).first().validations.filter(model_class_name=model_class_name).all()
        return cls.targets.get_targets(validations=validations, target=model_class_name)


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
            logger.exception(str(f"{self.name}:{self.phone_number}"))

class Customer(UserAccount):
    class Meta(ValidatableMixin.Meta):
        db_table = 'merchant_service_customers'

    received_sticker_pack = models.BooleanField(default=False)
    objects = models.Manager()




class Merchant(UserAccount):
    class Meta(UserAccount.Meta):
        db_table = 'merchant_service_users'
    merchant_description = models.TextField(blank=True, default="A Mobot Merchant")
    objects = models.Manager()


class MCStore(Trackable):
    name = models.TextField(blank=True, default="Coin Shop")
    description = models.TextField(blank=True, default="Mobot Store")
    privacy_policy_url = models.URLField(blank=True, default="https://mobilecoin.com/privacy")
    merchant_ref = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="store_owner")

    def __str__(self):
        return f'{self.name}:{self.phone_number}:store'


class CustomerStorePreferences(Trackable):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    store_ref = models.ForeignKey(MCStore, on_delete=models.CASCADE, related_name="stores")
    allows_contact = models.BooleanField()


@dataclass_json
@dataclass
class ProductMetadata:
    pass


class Size(str, Enum):
    SMALL = "SMALL"
    MEDIUM = "MEDIUM"
    LARGE = "LARGE"
    XL = "XL"
    XXL = "XXL"


@dataclass_json
@dataclass
class HoodieMetadata(ProductMetadata):
    size = Size


class ProductGroup(Trackable):
    """Example: A group of hoodies"""
    slug = models.SlugField(help_text="Short, unique descriptor", primary_key=True)
    name = models.TextField(help_text="A group of products offered together as a single product which may come in different descriptions/sizes")




class Product(Trackable):
    store_ref = models.ForeignKey(MCStore, on_delete=models.CASCADE)
    product_group = models.ForeignKey(ProductGroup, on_delete=models.CASCADE, null=True, blank=True, default=None, related_name="products")
    name = models.TextField(blank=False, null=False)
    description = models.TextField(default="Airdrop: Free mobilecoin!", blank=True, null=True)
    short_description = models.TextField(default="Airdrop", blank=False, null=False)
    image_link = models.URLField(default=None, blank=True, null=True)
    allows_refund = models.BooleanField(default=True, blank=False, null=False)
    price = MoneyField(max_digits=14, decimal_places=5, default_currency='GBP', help_text='Price of the product',
                       blank=False, default=1.0)
    objects = models.Manager()

    class Meta:
        app_label = 'merchant_services'
        abstract = False
        default_related_name = 'products'

    def has_inventory(self) -> bool:
        return self.inventory.count() > 0

    def add_inventory(self, number: int) -> QuerySet:
        created = InventoryItem.objects.bulk_create([
            InventoryItem(product_ref=self) for _ in range(number)
        ])
        return created

    @classmethod
    @atomic
    def add_to_cart(cls, id: str, customer: Customer):
        item = cls.objects.filter(id).inventory.filter(state__in=[InventoryItem.InventoryState.AVAILABLE]).first()
        order: Order = item.add_to_customer_cart(customer)
        return order


class Cart(Trackable):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, blank=False, null=False, db_index=True, related_name="cart")


class CartItem(Trackable):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    expires_after = models.IntegerField(help_text="Expires_after_secs, default 3600")


class Shipment(Trackable):
    class State(models.IntegerChoices):
        CREATED = -1, 'created'
        ADDRESS_RECEIVED = 0, 'address_received'
        ADDRESS_CONFIRMED = 1, 'address_confirmed'
        SHIPPED = 2, 'shipped'

    state = FSMIntegerField(default=State.CREATED, choices=State.choices)
    tracking_number = models.TextField(help_text="Tracking number for texts", blank=False, null=False)
    carrier = models.TextField(help_text="Carrier ID", blank=False, null=False)
    address = AddressField(help_text="Customer shipping address", blank=False, null=False)

    @transition(state, source=State.CREATED, target=State.ADDRESS_CONFIRMED)
    def confirm_address(self, address: Address):
        self.address = address
        self.address.save()
        self.address.raw



class InventoryItem(Trackable):
    class InventoryState(models.IntegerChoices):
        AVAILABLE = 1, 'Available'
        IN_CART = 0, 'In_Cart'
    state = FSMIntegerField(default=InventoryState.AVAILABLE, choices=InventoryState.choices)
    product_ref = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="inventory")
    description = models.TextField(help_text="Specifics on this inventory item")

    @transition(state, source=InventoryState.AVAILABLE, target=InventoryState.IN_CART)
    def add_to_customer_cart(self, customer: Customer):
        cart_item = Order.objects.create_order(item=self, customer=customer)
        self.state = InventoryItem.InventoryState.IN_CART
        self.cart_item = cart_item
        self.save()
        return cart_item


class OrderManager(models.Manager):
    def get_queryset(self):
        return super(models.Manager, self).get_queryset()

    def create_order(self, item, customer):
        order = self.create(item=item, customer=customer, price=item.product_ref.price)
        print(order)
        return order

class Order(Trackable):
    class State(models.IntegerChoices):
        STATUS_NEW = 0, 'new'
        STATUS_IN_CART = 1, 'in_cart'
        STATUS_PAYMENT_REQUESTED = 2, 'payment_requested'
        STATUS_PAYMENT_RECEIVED = 3, 'payment_received'
        STATUS_ORDER_AWAITING_SHIPMENT = 4, 'awaiting_shipment'
        STATUS_ORDER_SHIPPED = 5


    item = models.OneToOneField(InventoryItem, on_delete=models.DO_NOTHING, blank=False, null=False, related_name="orders", db_index=True)
    customer = models.ForeignKey(Customer, on_delete=models.DO_NOTHING, blank=False, null=False, db_index=True)
    price = MoneyField(blank=False, null=False, max_digits=14, decimal_places=5)
    state = FSMIntegerField(choices=State.choices, default=State.STATUS_NEW, protected=True)
    expiration = models.DateTimeField(auto_now_add=True)
    shipment = models.OneToOneField(Shipment, related_name="shipment", on_delete=models.CASCADE, blank=True, null=True)
    objects = OrderManager()

    @transition(state, source=[State.STATUS_NEW, State.STATUS_PAYMENT_REQUESTED], target=State.STATUS_PAYMENT_RECEIVED)
    def pay(self, amount: Money):
        print(f"Order paid for: {self} by customer: {self.customer}")
        pass

    @transition(state, source=[State.STATUS_PAYMENT_RECEIVED], target=State.STATUS_ORDER_SHIPPED)
    def ship(self):
        pass

    def add_order(self, customer):
        all = self.objects
        return all



class CampaignGroup(ValidatableMixin):
    name = models.TextField(help_text="Campaign group name", blank=False, null=False)


class Campaign(ValidatableMixin):
    name = models.TextField(help_text="Campaign name", null=False, blank=False)
    product_group = models.ForeignKey(ProductGroup, on_delete=models.CASCADE, related_name="campaigns", db_index=True)
    pre_drop_description = models.TextField(default="MobileCoin Product Drop")
    advertisement_start_time = models.DateTimeField(auto_now=True)
    start_time = models.DateTimeField(default=tz.now())
    end_time = models.DateTimeField(default=tz.now() + datetime.timedelta(days=1))
    quota = models.PositiveIntegerField(default=10, help_text="Total number we want to sell for this campaign")
    adjusted_price = MoneyField(max_digits=14, default=None, decimal_places=5, default_currency="PMB", blank=True, null=True)
    campaign_groups = models.ManyToManyField(CampaignGroup, related_name="campaigns")

    def _get_targets(self, model_class):
        return Campaign.get_campaign_targets(self.id, model_class_name=model_class)

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
            return self.product_group.price

    def __str__(self):
        return str(f"Campaign({self.id}, {self.name})")


class OfferSession(ValidatableMixin):
    class State(models.IntegerChoices):
        CREATED = -3, 'created'
        OFFERED = -2, 'offered'
        ACCEPTED = -1, 'accepted'
        CANCELED = 0, 'canceled'
        EXPIRED = 1, 'expired'

    state = FSMIntegerField(choices=State.choices, default=State.CREATED)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, blank=False, null=False, db_index=True, related_name="offer_sessions")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, blank=False, null=False, db_index=True, related_name="offer_sessions")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, blank=True, null=False, related_name="offer_sessions", db_index=True)
    cart = models.OneToOneField(Cart, on_delete=models.CASCADE)

    def _has_inventory(self):
        self.product.inventory > 0

    @transition(field=state, source=State.CREATED, target=State.OFFERED, conditions=[_has_inventory])
    def offer_to_customer(self, customer):
        self.campaign.product_group.inventory
        

class CampaignSession(ValidatableMixin):
    class State(models.IntegerChoices):
        CAMPAIGN_SESSION_CREATED = -3, 'created'
        CAMPAIGN_SESSION_OFFERED = -2, 'offered'
        CAMPAIGN_SESSION_CANCELLED = -1, 'cancelled'
        CAMPAIGN_ALLOW_CONTACT_REQUESTED = 2, 'allow_contact_requested'
        CAMPAIGN_ALLOW_CONTACT_COMPLETED = 3, 'allow_contact_completed'
        CAMPAIGN_SESSION_ACCEPTED = 4, 'accepted'

    state = FSMIntegerField(choices=State.choices, default=State.CAMPAIGN_SESSION_CREATED)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, blank=False, null=False, db_index=True, related_name="campaign_sessions")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, blank=False, null=False, db_index=True, related_name="campaign_sessions")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, blank=True, null=False, related_name="campaign_sessions")

    def _has_inventory(self):
        return True

    @transition(field=state, source=State.CAMPAIGN_SESSION_CREATED, target=State.CAMPAIGN_SESSION_OFFERED, conditions=[_has_inventory])
    def offer_to_customer(self, customer):
        self.campaign.product_group.inventory
