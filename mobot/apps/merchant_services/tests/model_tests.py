import logging

from django.test import TestCase, override_settings
from unittest.mock import Mock
from typing import List
import datetime
from moneyed import Money, GBP
from decimal import Decimal
from mobot.apps.merchant_services.models import Customer, Merchant, MCStore, Campaign, Validation, Sale, InventoryItem, Product
from django.db import transaction
from django.conf import settings
from django.utils import timezone as tz


@override_settings(DEBUG=True, TEST=True)
class CustomerTestCase(TestCase):

    def __init__(self, *args, **kwargs):
        super(CustomerTestCase, self).__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)

    def teardDown(self) -> None:
        Customer.objects.all().delete()
        Merchant.objects.all().delete()
        Campaign.objects.all().delete()
        MCStore.objects.all().delete()
        Validation.objects.all().delete()

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

    def _add_airdrop_product(self, price: Money):
        product = Product(name=f"MobileCoin Airdrop - {price}", price=price, description=f"A MOB giveaway: {price}", store_ref=self.store)
        product.save()
        return product

    def add_default_campaigns(self, store: MCStore) -> List[Campaign]:
        airdrop_product = self._add_airdrop_product(Money(-3.0, GBP))
        airdrop_product.save()

        original_drop = Campaign.objects.create(
                            name="Test AirDrop",
                            product_ref=airdrop_product,
                            pre_drop_description="Get free MOB from MobileCoin!",
                            advertisement_start_time=tz.make_aware(datetime.datetime.now(), tz.get_current_timezone()),
                            start_time=tz.make_aware(datetime.datetime.now(), tz.get_current_timezone()),
                            end_time=tz.make_aware(datetime.datetime.now() + datetime.timedelta(days=3.0), tz.get_current_timezone()),
                            adjusted_price=Money(-3.0, "GBP"),
                            quota=100)

        bonus_drops = [Campaign.objects.create(
                            name=f"Test Bonus AirDrop {product.price}",
                            pre_drop_description=f"Test Bonus Drop {product.price}",
                            product_ref=product,
                            advertisement_start_time=tz.make_aware(datetime.datetime.now(), tz.get_current_timezone()),
                            start_time=tz.make_aware(datetime.datetime.now(), tz.get_current_timezone()),
                            end_time=tz.make_aware(datetime.datetime.now() + datetime.timedelta(days=3.0), tz.get_current_timezone()),
                            quota=quota,
                            adjusted_price=product.price) for quota, product in [(80, self._add_airdrop_product(2.0)), (10, self._add_airdrop_product(7.0)), (7, self._add_airdrop_product(22.0)), (3, self._add_airdrop_product(47))]]

        return original_drop, bonus_drops

    def _test_add_customer_validation(self, campaign: Campaign):
        validation = Validation(model_class_name=Customer.__name__, model_attribute_name="phone_number", comparator_func="startswith", target_value="+44")
        validation.save()
        campaign.validations.add(validation)
        return validation

    def setUp(self):
        self.merchant = self.add_default_merchant()
        self.store = self.add_default_store(self.merchant)
        self.cust_us = self.add_default_customer("Greg", phone_number="+18054412653")
        self.cust_uk = self.add_default_customer("Adam", phone_number="+447441433906")
        self.original_drop, self.bonus_drops = self.add_default_campaigns(self.store)

    def test_can_create_drop_session(self):
        greg = Customer.objects.get(name="Greg")
        adam = Customer.objects.get(name="Adam")
        print(greg)
        print(adam)

    def test_can_add_44_validation(self):
        original_drop: Campaign = self.original_drop
        validation = self._test_add_customer_validation(original_drop)
        validation.save()
        print(validation)
        original_drop.validations.add(validation)
        original_drop.save()
        print(original_drop.validations)
        targets = original_drop.get_target_customers()

        print(targets)