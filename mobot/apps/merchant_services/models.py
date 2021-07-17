import datetime
import importlib

from django.db import models
from typing import TypeVar
import logging
from django.conf import settings
from django.db.models import Q, QuerySet
from django.utils import timezone as tz
from django_fsm import FSMIntegerField, transition
from djmoney.models.fields import MoneyField
from moneyed import Money
from phonenumber_field.modelfields import PhoneNumberField
from address.models import AddressField
from address.models import Address
from django.db.transaction import atomic

from mobot.apps.payment_service.models import Payment
from mobot.lib.currency import MOB, PMOB

from django.contrib.auth.models import User
from mobot.signald_client import Signal

T = TypeVar('T', bound=models.Model)

logger = logging.getLogger("MerchantServices")
logger.setLevel(settings.LOG_LEVEL)


class Trackable(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

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
        validations = cls.objects.filter(id=campaign_id).first().validations.filter(
            model_class_name=model_class_name).all()
        return cls.targets.get_targets(validations=validations, target=model_class_name)


class UserAccount(ValidatableMixin):
    phone_number = PhoneNumberField(primary_key=True)
    name = models.TextField(blank=False, null=False)

    class Meta(ValidatableMixin.Meta):
        app_label = 'merchant_services'

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

    def __str__(self):
        return f"Customer({self.name}, {self.phone_number})"


class Merchant(UserAccount):
    class Meta(UserAccount.Meta):
        db_table = 'merchant_service_users'

    merchant_description = models.TextField(blank=True, default="A Mobot Merchant")
    objects = models.Manager()

    def __str__(self):
        return f"Merchant({self.name}, {self.phone_number})"


class MobotStore(Trackable):
    name = models.TextField(blank=True, null=True, default="Mobot Shop")
    description = models.TextField(blank=True, null=True, default="Mobot Shop sells all kinds of goodies")
    privacy_policy_url = models.URLField(blank=True, default="https://mobilecoin.com/privacy")
    merchant_ref = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="store_owner")

    def __str__(self):
        return f'{self.name}:{self.description}{self.merchant_ref.phone_number}:store'


class CustomerStorePreferences(Trackable):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    store = models.ForeignKey(MobotStore, on_delete=models.CASCADE, related_name="stores")
    allows_contact = models.BooleanField(default=False)


class ProductGroup(Trackable):
    """Example: A group of hoodies"""
    name = models.TextField(
        help_text="A group of products offered together as a single product which may come in different descriptions/sizes")

    @property
    def inventory(self):
        self.products.all()


class Product(Trackable):
    store = models.ForeignKey(MobotStore, on_delete=models.CASCADE)
    product_group = models.ForeignKey(ProductGroup, on_delete=models.CASCADE, null=True, blank=True, default=None,
                                      related_name="products")
    name = models.TextField(blank=False, null=False, default="Hoodie(M)")
    description = models.TextField(default="Mobilecoin Original Hoodie, Size M", blank=True, null=True)
    short_description = models.TextField(default="Hoodie, Size M", blank=False, null=False)
    image_link = models.URLField(default=None, blank=True, null=True)
    allows_refund = models.BooleanField(default=True, blank=False, null=False)
    price = MoneyField(max_digits=14, decimal_places=5, default_currency=PMOB, help_text='Price of the product in PMOB',
                       blank=False, default=0.0)
    metadata = models.JSONField(blank=False, null=False, db_index=True, default=dict)

    class Meta:
        app_label = 'merchant_services'
        abstract = False
        default_related_name = 'products'

    @property
    def available(self) -> int:
        return self.inventory.filter(order=None).count()

    def has_inventory(self) -> bool:
        return self.inventory.filter(order=None).count() > 0

    def add_inventory(self, number: int, sku: str = None) -> QuerySet:
        if not sku:
            sku = f"{self.id}-item"
        created = InventoryItem.objects.bulk_create([
            InventoryItem(product=self, sku=sku) for _ in range(number)
        ])
        return created


class InventoryItem(Trackable):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="inventory")
    sku = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    is_ordered = models.BooleanField(default=False)
    date_ordered = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Inventory Item {self.sku}"


class OutOfStockException(Exception):
    pass


class OrderManager(models.Manager):
    @atomic
    def order_product(self, product: Product, customer: Customer) -> QuerySet:
        order = self.create(customer=customer, product=product)
        try:
            inventory_item = InventoryItem.objects.get(order=None, product=product)
            inventory_item.order = order
            inventory_item.save()
        except InventoryItem.DoesNotExist:
            order.delete()
            raise OutOfStockException(f"All out of {product}!")
        order.save()
        return order


class Order(Trackable):
    class State(models.IntegerChoices):
        NEW = 0, 'new'
        AWAITING_SHIPMENT_INFO = 1, 'awaiting_shipment_info'
        SHIPPING_INFO_RECEIVED = 2, 'shipment_info_received'
        PAYMENT_REQUESTED = 3, 'awaiting_payment'
        PAYMENT_RECEIVED = 4, 'payment_received'
        OVERPAID = 5, 'overpaid'

    state = FSMIntegerField(choices=State.choices, default=State.NEW)
    item = models.OneToOneField(InventoryItem,
                                related_name="order", db_index=True, blank=True, null=True, on_delete=models.CASCADE,
                                unique=True)
    product = models.ForeignKey(Product, on_delete=models.DO_NOTHING, blank=False, null=False)
    customer = models.ForeignKey(Customer, on_delete=models.DO_NOTHING, blank=False, null=False, db_index=True)
    address = AddressField(blank=True, null=True)
    payment = models.OneToOneField(Payment, related_name="order", on_delete=models.DO_NOTHING, blank=True, null=True)
    objects = OrderManager()

    @property
    def overpayment_amount(self) -> Money:
        return self.payment.amount - self.product.price

class CampaignGroup(ValidatableMixin):
    name = models.TextField(help_text="Campaign group name", blank=False, null=False)


class CampaignManager(models.Manager):
    def active_campaigns_by_store(self, store: MobotStore) -> QuerySet:
        super().get_queryset().filter(store=store)


class Campaign(ValidatableMixin):
    name = models.TextField(help_text="Campaign name", null=False, blank=False)
    product_group = models.ForeignKey(ProductGroup, on_delete=models.CASCADE, related_name="campaigns", db_index=True)
    pre_drop_description = models.TextField(default="MobileCoin Hoodies")
    advertisement_start_time = models.DateTimeField(auto_now=True)
    start_time = models.DateTimeField(auto_now=True)
    end_time = models.DateTimeField(default=tz.now() + datetime.timedelta(days=1))
    quota = models.PositiveIntegerField(default=100, help_text="Total number we want to sell for this campaign")
    adjusted_price = MoneyField(max_digits=14, default=None, decimal_places=5, default_currency="PMB", blank=True,
                                null=True)
    number_restriction = models.CharField(max_length=3)
    store = models.ForeignKey(MobotStore, on_delete=models.DO_NOTHING, db_index=True)
    campaign_groups = models.ManyToManyField(CampaignGroup, related_name="campaigns")
    objects = CampaignManager()

    @property
    def description(self) -> str:
        return self.pre_drop_description

    @property
    def not_active_yet(self) -> bool:
        return tz.now() <= self.start_time

    @property
    def is_expired(self):
        return tz.now() >= self.end_time

    @property
    def is_active(self) -> bool:
        return self.start_time <= tz.now() <= self.end_time

    def _get_targets(self, model_class) -> QuerySet:
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


class DropSessionManager(models.Manager):
    def create(self, **obj_data):
        phone_number = obj_data['phone_number']
        campaign = obj_data.get['campaign']
        customer, _ = Customer.objects.get_or_create(phone_number=phone_number)
        return super().create(customer=customer, campaign=campaign)


class DropSession(Trackable):
    class State(models.IntegerChoices):
        CANCELED = -2, 'canceled'
        EXPIRED = -1, 'expired'
        FAILED = -3, 'failed'  # Customer offered product, customer unable to buy product due to shipping
        CREATED = 0, 'created' # Greeting has begun
        OFFERED = 1, 'offered'
        ACCEPTED = 2, 'accepted'
        NOT_READY = 3, 'not_ready'

    state = FSMIntegerField(choices=State.choices, default=State.CREATED)
    campaign = models.ForeignKey(Campaign, on_delete=models.DO_NOTHING, blank=False, null=False, db_index=True,
                                 related_name="drop_sessions")
    customer = models.ForeignKey(Customer, on_delete=models.DO_NOTHING, blank=False, null=False, db_index=True,
                                 related_name="drop_sessions")
    product = models.ForeignKey(Product, on_delete=models.DO_NOTHING, blank=True, null=True,
                                related_name="drop_sessions", db_index=True)
    objects = DropSessionManager()

    @property
    def has_inventory(self):
        self.product.inventory.all() > 0
