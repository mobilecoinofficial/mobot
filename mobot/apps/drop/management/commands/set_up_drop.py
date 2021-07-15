from django.core.management.base import BaseCommand, CommandError
from typing import Dict, Iterable
import phonenumbers
from phonenumbers import PhoneNumber
from mobot.lib.currency import *
from decimal import Decimal
from django.conf import settings

from ..commands import *
import json
from enum import Enum


class DropManagmentActions(str, Enum):
    CREATE_STORE = 'create-store'
    ADD_INVENTORY = 'add-inventory'
    UPDATE_INVENTORY = 'update-inventory'
    ADD_PRODUCT = 'add-product'
    ADD_CAMPAIGN = 'add-campaign'

class Command(BaseCommand):
    help = 'Add inventory, drops, etc.'
    def __init__(self, *args, **kwargs):
        self.product: Product = None
        self.store: Store = None
        self.merchant: Merchant = None
        self.product_group: ProductGroup = None
        self.orders: Iterable[Order] = []
        super().__init__(*args, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument('-a', '--action', choices=DropManagmentActions, type=DropManagmentActions)
        parser.add_argument('-n', '--store-phone-number', type=phonenumbers.parse, required=True)
        parser.add_argument('-s', '--store-name', type=str, required=False)
        parser.add_argument('-p', '--product-name', type=str, help="Name of the product group", required=False, default="Hoodie")
        parser.add_argument('-i', '--inventory', type=json.loads, help="JSON of the inventory for the product at various sizes; e.g '{'S': 10, 'M': 10, 'L': 10 }'", default='{}')
        parser.add_argument('-d', '--description', required=False)
        parser.add_argument('--price', required=False, type=Decimal)
        parser.add_argument('--currency', default=GBP)

    def _load_sizes(self, inventory: Dict[str, int]) -> Dict[Size, int]:
        sized = dict()
        for key, value in inventory.items():
            sized[Size(key)] = value
        return sized

    def add_or_get_store(self, phone_number: PhoneNumber = None, store_name: str = None) -> Store:
        store, created = Store.objects.get_or_create(phone_number=phone_number)
        if created:
            if store_name:
                store.name = store_name
            store.save()
        return store

    def add_products(self, product_group_name: str, inventory: Dict[Size, int]):
        pass

    def _add_sized_product(self, product_group: ProductGroup, size: str, price: Money = Money(Decimal(25.0), currency=GBP)) -> Product:
        hoodie_product, created = Product.objects.get_or_create(
            name=f"Hoodie Size {size}",
            price=price,
            description=f"MobileCoin Hoodie {size}",
            product_group=product_group,
            store_ref=self.store,
            metadata=dict(size=size)
        )
        return hoodie_product

    def handle(self, *args, **options):
        self.inventory = self._load_sizes(options.get('inventory'))
        self.product_name = options.get('product_name')
        self.store_name = options.get('store_name')
        self.store_phone_number = options.get('store_phone_number')
        self.action = options.get('action')
        self.store = None
        self.product = None
        price = options.get('price')
        currency = options.get('currency')

        if self.action == DropManagmentActions.CREATE_STORE:
            self.store = self.add_or_get_store(self.store_phone_number, self.store_name)

        if self.action == DropManagmentActions.ADD_PRODUCT:
            self.product, created = ProductGroup.objects.get_or_create(name=self.product_name)

        if self.action == DropManagmentActions.UPDATE_INVENTORY:
            if not all(self.product_name, price, currency):
                raise CommandError("Lacking product name; can't create product")
            else:
                self.product_group = ProductGroup.objects.get(name=self.product_name)
                for size, amt_available in self.inventory:
                    price = Money(options.get('price'), options.get('currency'))
                    product = self._add_sized_product(product_group=self.product_group, price=price, size=size)
                    product.add_inventory(amt_available)






