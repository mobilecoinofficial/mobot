import logging

from django.test import TestCase, override_settings
from unittest.mock import Mock
from typing import List
import datetime
from moneyed import Money, GBP, Currency
from decimal import Decimal
from django.utils import timezone as tz
from dataclasses import dataclass
from mobot.apps.merchant_services.models import Customer, Merchant, Store, Product, ProductGroup, DropSession, InventoryItem, Campaign, CampaignGroup, Validation


STORE_PHONE_NUMBER = "+447441433907"
CUST_UK_NUMBER = "+447441433906"
CUST_US_NUMBER = "+18054412653"

@dataclass
class Airdrop:
    price: Decimal
    quota: int
    currency: Currency = GBP


class StoreFixtures:

    def __init__(self):
        self.merchant = self.add_default_merchant(STORE_PHONE_NUMBER)
        self.store = self.add_default_store(self.merchant)
        self.cust_us = self.add_default_customer("Greg", phone_number="+18054412653")
        self.cust_uk = self.add_default_customer("Adam", phone_number="+447441433906")
        self.original_drop, self.airdrop_product = self.add_default_campaign()
        self.hoodie_product_group = StoreFixtures.add_hoodie_product_group()

    def _add_hoodie(self, size: str, price: Money = Money(Decimal(15.0), currency=GBP)) -> Product:
        hoodie_product, created = Product.objects.get_or_create(
            name=f"MobileCoin Hoodie - {size}",
            price=price,
            description=f"MobileCoin Hoodie {size}",
            product_group=self.hoodie_product_group,
            store_ref=self.store,
            metadata=dict(size=size)
        )
        return hoodie_product

    @staticmethod
    def add_inventory(product: Product, number: int = 10) -> List[InventoryItem]:
        inv = product.add_inventory(20)
        return inv


    @staticmethod
    def add_hoodie_product_group():
        product_group = ProductGroup(name="MC Hoodie")
        product_group.save()
        return product_group

    def add_default_customer(self, name: str, phone_number: str = "+18054412653") -> Customer:
        try:
            c = Customer.objects.create(phone_number=phone_number, name=name)
            c.save()
            if c:
                return c
        except TypeError as e:
            self.logger.exception(f"{name}:{phone_number}")

    def add_default_store(self, merchant: Merchant) -> Store:
        s, created = Store.objects.get_or_create(merchant_ref=merchant, name="Test MobileCoin Coin Drop Store")
        s.save()
        return s

    def add_default_merchant(self, phone_number: str = STORE_PHONE_NUMBER) -> Merchant:
        m, created = Merchant.objects.get_or_create(name="Test MobileCoin Official Merchant", phone_number=phone_number)
        m.save()
        return m

    def add_customer_44_validation(self, campaign: Campaign):
        validation = Validation(model_class_name=Customer.__name__, model_attribute_name="phone_number", comparator_func="startswith", target_value="+44")
        validation.save()
        campaign.validations.add(validation)
        return validation

    def add_product_validation(self, campaign: Campaign):
        validation = Validation(model_class_name=Product.__name__, model_attribute_name="inventory", comparator_func="gt", target_value="0")
        validation.save()
        campaign.validations.add(validation)
        return validation


    def add_airdrop_product(self, airdrop: Airdrop, group: ProductGroup = ProductGroup("Bonus Aidrop")):
        product = Product(name=f"MobileCoin Airdrop - {airdrop.price}", product_group=group, price=Money(airdrop.price, airdrop.currency), description=f"A MOB giveaway: {airdrop.price} {airdrop.currency}", store_ref=self.store)
        items = [InventoryItem(product=product) for _ in range(airdrop.quota)]
        product.save()
        return airdrop.quota, product

    def add_default_campaign(self) -> List[Campaign]:
        product_group = ProductGroup(name="Aidrop Original")
        quota, airdrop_product = self.add_airdrop_product(Airdrop(price=-3.0, currency=GBP, quota=100), group=product_group)

        original_drop = Campaign.objects.create(
                            name="Test AirDrop",
                            product_group=product_group,
                            store=self.store,
                            pre_drop_description="Get free MOB from MobileCoin!",
                            advertisement_start_time=tz.make_aware(datetime.datetime.now(), tz.get_current_timezone()),
                            start_time=tz.make_aware(datetime.datetime.now(), tz.get_current_timezone()),
                            end_time=tz.make_aware(datetime.datetime.now() + datetime.timedelta(days=3.0), tz.get_current_timezone()),
                            adjusted_price=Money(-3.0, "GBP"),
                            quota=100)

        return original_drop, airdrop_product

