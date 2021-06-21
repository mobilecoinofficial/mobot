from django.test import TestCase
from typing import List
import datetime
from moneyed import Money
from decimal import Decimal
from moneyed import GBP
from phonenumbers import PhoneNumber
import phonenumbers
from mobot.apps.merchant_services.models import Customer, Merchant, MCStore, Drop, Campaign, Validation


class CustomerTestCase(TestCase):

    def add_default_customer(self, phone_number: PhoneNumber, name: str ="A Test Customer") -> Customer:
        c, created = Customer.objects.get_or_create(name=name, phone_number=phone_number)
        return c

    def add_default_store(self, merchant: Merchant) -> MCStore:
        s, created = MCStore.objects.get_or_create(merchant_ref=merchant, name="Test MobileCoin Coin Drop Store")
        s.save()
        return s

    def add_default_merchant(self) -> Merchant:
        m, created = Merchant.objects.get_or_create(name="Test MobileCoin Official Merchant", phone_number="+44 07911 123456")
        m.save()
        return m

    def add_default_drops(self, store: MCStore) -> List[Drop]:
        original_drop, _ = Drop.objects.update_or_create(name="Test AirDrop",
                            pre_drop_description="Get free MOB from MobileCoin!",
                            store_ref=store,
                            description="Test Airdrop 3.0 GBP",
                            number_restriction=["+44"],
                            advertisement_start_time=datetime.datetime.utcnow(),
                            start_time=datetime.datetime.utcnow(),
                            end_time=datetime.datetime.utcnow() + datetime.timedelta(days=3.0),
                            price=Money(Decimal(3.0), GBP),
                            quota=100)


        bonus_drops = [Drop.objects.update_or_create(name=f"Test Bonus AirDrop {price}",
                            pre_drop_description="Get free MOB from MobileCoin!",
                            store_ref=store,
                            description=f"Test Bonus Drop {price}",
                            number_restriction=["+44"],
                            advertisement_start_time=datetime.datetime.utcnow(),
                            start_time=datetime.datetime.utcnow(),
                            end_time=datetime.datetime.utcnow() + datetime.timedelta(days=3.0),
                            quota=quota,
                            price=Money(Decimal(price), GBP)) for quota, price in [(80, 2.0), (10, 7.0), (7, 22.0), (3, 47)]]

        return original_drop, bonus_drops

    def setUp(self):
        self.merchant = self.add_default_merchant()
        self.store = self.add_default_store(self.merchant)
        self.cust_us = self.add_default_customer(name="Greg", phone_number=phonenumbers.parse("+18054412653"))
        self.cust_uk = self.add_default_customer(name="Adam", phone_number=phonenumbers.parse("+44 07911 654321"))
        self.original_drop, self.bonus_drops = self.add_default_drops(self.store)

    def test_can_create_drop_session(self):
        greg = Customer.objects.get(name="Greg")
        adam = Customer.objects.get(name="Adam")
        print(greg)
        print(adam)