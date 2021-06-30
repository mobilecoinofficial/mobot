import logging

from django.test import TestCase, override_settings
from unittest.mock import Mock
from typing import List
import datetime
from moneyed import Money, GBP, Currency
from decimal import Decimal
from django.utils import timezone as tz
from dataclasses import dataclass
import django
django.setup()
from mobot.apps.merchant_services.models import Customer, MCStore, Merchant, Product, InventoryItem, Campaign, Validation, ProductGroup, Order


@dataclass
class Airdrop:
    price: Decimal
    quota: int
    currency: Currency = GBP

@override_settings(DEBUG=True, TEST=True)
class CustomerTestCase(TestCase):

    def __init__(self, *args, **kwargs):
        super(CustomerTestCase, self).__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)

    def teardDown(self) -> None:
        Customer.objects.all().delete()
        Merchant.objects.all().delete()
        Product.objects.all().delete()
        InventoryItem.objects.all().delete()

    def add_default_customer(self, name: str, phone_number: str = "+18054412653") -> Customer:
        try:
            c = Customer.objects.create(phone_number=phone_number, name=name)
            c.save()
            if c:
                return c
        except TypeError as e:
            self.logger.exception(f"{name}:{phone_number}")

    def add_default_store(self, merchant: Merchant) -> MCStore:
        s, created = MCStore.objects.get_or_create(merchant_ref=merchant, name="Test MobileCoin Coin Drop Store")
        s.save()
        return s

    def add_default_merchant(self) -> Merchant:
        m, created = Merchant.objects.get_or_create(name="Test MobileCoin Official Merchant", phone_number="447441433907")
        m.save()
        return m

    def _add_airdrop_product(self, airdrop: Airdrop, group: ProductGroup = ProductGroup("Bonus Aidrop")):
        product = Product(name=f"MobileCoin Airdrop - {airdrop.price}", product_group=group, price=Money(airdrop.price, airdrop.currency), description=f"A MOB giveaway: {airdrop.price} {airdrop.currency}", store_ref=self.store)
        items = [InventoryItem(product_ref=product) for _ in range(airdrop.quota)]
        product.save()
        return airdrop.quota, product

    def _add_campaign_for_drop_drop(self, drop: Airdrop):
        Campaign.objects.create(
            name=f"Test Bonus AirDrop {drop.price}",
            pre_drop_description=f"Test Bonus Drop {drop.price}",
            product_ref=drop,
            advertisement_start_time=tz.make_aware(datetime.datetime.now(), tz.get_current_timezone()),
            start_time=tz.make_aware(datetime.datetime.now(), tz.get_current_timezone()),
            end_time=tz.make_aware(datetime.datetime.now() + datetime.timedelta(days=3.0), tz.get_current_timezone()),
            quota=drop.quota,
            adjusted_price=None
        )

    def add_default_campaign(self, store: MCStore) -> List[Campaign]:
        product_group = ProductGroup(name="Aidrop Original")
        quota, airdrop_product = self._add_airdrop_product(Airdrop(price=-3.0, currency=GBP, quota=100), group=product_group)

        original_drop = Campaign.objects.create(
                            name="Test AirDrop",
                            product_group=product_group,
                            pre_drop_description="Get free MOB from MobileCoin!",
                            advertisement_start_time=tz.make_aware(datetime.datetime.now(), tz.get_current_timezone()),
                            start_time=tz.make_aware(datetime.datetime.now(), tz.get_current_timezone()),
                            end_time=tz.make_aware(datetime.datetime.now() + datetime.timedelta(days=3.0), tz.get_current_timezone()),
                            adjusted_price=Money(-3.0, "GBP"),
                            quota=100)

        return original_drop

    def _test_add_customer_validation(self, campaign: Campaign):
        validation = Validation(model_class_name=Customer.__name__, model_attribute_name="phone_number", comparator_func="startswith", target_value="+44")
        validation.save()
        campaign.validations.add(validation)
        return validation

    def _test_add_product_validation(self, campaign: Campaign):
        validation = Validation(model_class_name=Product.__name__, model_attribute_name="inventory", comparator_func="gt", target_value="0")
        validation.save()
        campaign.validations.add(validation)
        return validation

    def _test_add_hoodie_product_group(self):
        product_group = ProductGroup(name="MC Hoodie")
        product_group.save()
        return product_group

    def _add_hoodie(self, size: str, price: Money = Money(Decimal(15.0), currency=GBP)):
        hoodie_product, created = Product.objects.get_or_create(
            name=f"MobileCoin Hoodie - {size}",
            price=price,
            description=f"MobileCoin Hoodie {size}",
            product_group=self.hoodie_product_group,
            store_ref=self.store,
        )
        return hoodie_product

    def _add_inventory(self, product: Product, number: int = 10) -> List[InventoryItem]:
        inv = product.add_inventory(20)
        return inv

    def _add_hoodie_to_customer(self, product: Product, customer: Customer) -> Order:
        return Product.add_to_cart(customer)


    def setUp(self):
        self.merchant = self.add_default_merchant()
        self.store = self.add_default_store(self.merchant)
        self.cust_us = self.add_default_customer("Greg", phone_number="+18054412653")
        self.cust_uk_2 = self.add_default_customer("Bpb", phone_number="+447441433907")
        self.cust_uk = self.add_default_customer("Adam", phone_number="+447441433906")
        self.original_drop = self.add_default_campaign(self.store)
        self.hoodie_product_group = self._test_add_hoodie_product_group()

    def test_can_create_drop_session(self):
        greg = Customer.objects.get(name="Greg")
        adam = Customer.objects.get(name="Adam")

    def test_can_add_44_validation_and_find_customers(self):
        original_drop: Campaign = self.original_drop
        validation = self._test_add_customer_validation(original_drop)
        validation.save()
        original_drop.validations.add(validation)
        original_drop.save()
        targets = original_drop.get_target_customers()
        for target in targets:
            print(target)
        self.assertEqual(2, len(targets))

    def test_can_create_hoodie_and_inventory(self):
        small_hoodie = self._add_hoodie(size="small")
        small_hoodie.add_inventory(2)
        small_hoodie.add_inventory(7)
        self.assertEqual(small_hoodie.inventory.count(), 9)

        medium_hoodie = self._add_hoodie(size="medium")
        medium_hoodie.add_inventory(5)
        medium_hoodie.add_inventory(10)
        self.assertEqual(medium_hoodie.inventory.count(), 15)

        large_hoodie = self._add_hoodie(size="large")
        large_hoodie.add_inventory(10)
        self.assertEqual(large_hoodie.inventory.count(), 10)

    def test_adding_hoodie_to_shopping_cart(self):
        small_hoodie = self._add_hoodie(size="small")
        small_hoodie.add_inventory(2)
        self.assertEqual(small_hoodie.inventory.count(), 2)
        order1 = self._add_hoodie_to_customer(small_hoodie, self.cust_uk)
        order1.save()
        self.assertEqual(small_hoodie.inventory.count(), 1)
        order2 = self._add_hoodie_to_customer(small_hoodie, self.cust_uk_2)
        order2.save()
        self.assertEqual(small_hoodie.inventory.count(), 0)
