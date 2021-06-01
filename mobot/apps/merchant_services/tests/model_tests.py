import logging

from django.test import TestCase, override_settings
from typing import List
from moneyed import Money, GBP
from decimal import Decimal
import django
django.setup()

from mobot.campaigns.hoodies import Size
from mobot.apps.merchant_services.models import Customer, Product, InventoryItem, Campaign, Order
from mobot.apps.merchant_services.tests.fixtures import StoreFixtures


@override_settings(DEBUG=True, TEST=True)
class CustomerTestCase(TestCase):

    def __init__(self, *args, **kwargs):
        super(CustomerTestCase, self).__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)

    def tearDown(self) -> None:
        Customer.objects.all().delete()
        Order.objects.all().delete()
        Product.objects.all().delete()
        InventoryItem.objects.all().delete()


    def _add_hoodie(self, size: str, price: Money = Money(Decimal(15.0), currency=GBP)) -> Product:
        hoodie_product, created = Product.objects.get_or_create(
            name=f"Hoodie {size}",
            price=price,
            description=f"MobileCoin Hoodie {size}",
            product_group=self.hoodie_product_group,
            store=self.store,
            metadata=dict(size=size)
        )
        return hoodie_product

    def _add_inventory(self, product: Product, number: int = 10) -> List[InventoryItem]:
        inv = product.add_inventory(20)
        return inv

    def setUp(self):
        self.basic_fixtures = StoreFixtures()
        self.merchant = self.basic_fixtures.merchant
        self.store = self.basic_fixtures.store
        self.cust_us = self.basic_fixtures.cust_us
        self.cust_uk = self.basic_fixtures.cust_uk

        self.original_drop = self.basic_fixtures.original_drop
        self.hoodie_product_group = self.basic_fixtures.hoodie_product_group

    def test_can_create_drop_session(self):
        greg = Customer.objects.get(name="Greg")
        adam = Customer.objects.get(name="Adam") # just to assert exists
        self.assertEqual(greg.phone_number, "+18054412653")
        self.assertEqual(greg.phone_number.country_code, 1)

    def test_can_add_44_validation_and_find_customers(self):
        original_drop: Campaign = self.original_drop
        validation = self.basic_fixtures.add_customer_44_validation(original_drop)
        validation.save()
        original_drop.validations.add(validation)
        original_drop.save()
        targets = original_drop.get_target_customers()
        for target in targets:
            print(target)
        self.assertEqual(2, targets.count())

    def test_can_create_hoodie_and_inventory(self):
        small_hoodie = self._add_hoodie(size=Size.S)
        small_hoodie.add_inventory(10)
        medium_hoodie = self._add_hoodie(size=Size.M)
        medium_hoodie.add_inventory(10)
        large_hoodie = self._add_hoodie(size=Size.L)
        large_hoodie.add_inventory(10)
        large = list(Product.objects.filter(metadata=dict(size=Size.L)))
        self.assertEqual(len(large), 1)
        inv = large_hoodie.inventory.all()
        self.assertEqual(len(inv), 10)

    def test_can_add_product_to_customer_order(self):
        from mobot.apps.merchant_services.models import OutOfStockException
        small_hoodie = self._add_hoodie(size=Size.S)
        small_hoodie.add_inventory(1)
        curr_inv = small_hoodie.inventory.filter(order=None).count()
        self.assertEqual(curr_inv, 1)
        customer = self.cust_uk
        order = Order.objects.order_product(product=small_hoodie, customer=customer)
        print(order)
        self.assertEqual(small_hoodie.available, curr_inv - 1)
        self.assertEqual(small_hoodie.available, 0)
        with self.assertRaises(OutOfStockException):
            new_order = Order.objects.order_product(product=small_hoodie, customer=customer)

    def test_can_parse_shipping_address(self):
        print("Not yet implemented!")
        pass





